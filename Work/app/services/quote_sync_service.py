# app/services/quote_sync_service.py
"""Bidirectional quote synchronization service with deduplication."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import traceback

from app.database.database import Database
from app.models.task import Task
from app.services.mongodb_service import MongoDBService
from app.services.work_service import WorkService
from app.services.notification_service import NotificationService


class QuoteSyncService:
    """Bidirectional quote synchronization between MongoDB and local SQLite."""

    def __init__(
        self,
        database: Database,
        mongodb: MongoDBService,
        work_service: WorkService,
        notification_service: NotificationService,
    ):
        self._database = database
        self._mongodb = mongodb
        self._work_service = work_service
        self._notifications = notification_service
        self._synced_references = set()

    def sync_quotes_from_mongodb(self) -> Dict[str, Any]:
        """Fetch quotes from MongoDB and sync to local SQLite."""
        if not self._mongodb.is_connected:
            return {"success": False, "message": "MongoDB not connected", "synced": 0}

        try:
            print("🔄 Fetching quotes from MongoDB...")
            quotes = self._mongodb.get_quotes(limit=200)
            print(f"📥 Found {len(quotes)} quotes in MongoDB")
            
            synced_count = 0
            updated_count = 0
            task_count = 0
            duplicate_count = 0
            errors = []

            self._synced_references.clear()

            for quote in quotes:
                try:
                    if "_id" in quote:
                        quote["_id"] = str(quote["_id"])
                    
                    reference = quote.get("reference")
                    if not reference:
                        continue
                    
                    if reference in self._synced_references:
                        duplicate_count += 1
                        continue
                    self._synced_references.add(reference)
                    
                    local_quote = self._get_local_quote(reference)
                    
                    if not local_quote:
                        self._create_local_quote(quote)
                        synced_count += 1
                        print(f"✅ Created local quote: {reference}")
                        
                        task = self._create_task_from_quote(quote)
                        if task:
                            task_count += 1
                            print(f"✅ Created task for quote: {reference} (Task ID: {task.id})")
                    else:
                        if self._needs_update(local_quote, quote):
                            self._update_local_quote(local_quote, quote)
                            updated_count += 1
                            print(f"🔄 Updated local quote: {reference}")

                    self._update_sync_timestamp(reference)
                    
                except Exception as e:
                    error_msg = f"Error processing quote {quote.get('reference', 'unknown')}: {e}"
                    print(f"❌ {error_msg}")
                    errors.append(error_msg)

            result_msg = (
                f"Synced {synced_count} new, updated {updated_count} existing, "
                f"created {task_count} tasks, skipped {duplicate_count} duplicates"
            )
            if errors:
                result_msg += f" (with {len(errors)} errors)"
                
            stats = self.get_quote_statistics()
            
            return {
                "success": True,
                "message": result_msg,
                "synced": synced_count,
                "updated": updated_count,
                "tasks_created": task_count,
                "duplicates_skipped": duplicate_count,
                "errors": errors,
                "statistics": stats
            }
            
        except Exception as e:
            print(f"❌ Error syncing from MongoDB: {e}")
            traceback.print_exc()
            return {"success": False, "message": str(e), "synced": 0}

    def _create_local_quote(self, quote: Dict[str, Any]) -> None:
        """Create a local record for a quote."""
        try:
            items = quote.get("items", [])
            if isinstance(items, list):
                cleaned_items = []
                for item in items:
                    if isinstance(item, dict):
                        cleaned_item = {}
                        for k, v in item.items():
                            if k != '_id':
                                cleaned_item[k] = v
                        cleaned_items.append(cleaned_item)
                    else:
                        cleaned_items.append(item)
                items_json = json.dumps(cleaned_items)
            else:
                items_json = json.dumps([])
            
            customer_name = quote.get("customerName") or quote.get("customer_name", "Unknown Customer")
            
            with self._database.connection() as conn:
                existing = conn.execute(
                    "SELECT reference FROM quotes WHERE reference = ?",
                    (quote.get("reference"),)
                ).fetchone()
                
                if existing:
                    print(f"⚠️ Quote {quote.get('reference')} already exists, skipping insert")
                    return
                
                conn.execute(
                    """
                    INSERT INTO quotes (
                        reference, customer_name, company, email, phone,
                        notes, items, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        quote.get("reference"),
                        customer_name,
                        quote.get("company", ""),
                        quote.get("email", ""),
                        quote.get("phone", ""),
                        quote.get("notes", ""),
                        items_json,
                        self._map_status_to_local(quote.get("status", "received")),
                        quote.get("createdAt", datetime.now().isoformat())
                    )
                )
                conn.commit()
                print(f"✅ Created local quote: {quote.get('reference')} - {customer_name}")
                
        except Exception as e:
            print(f"❌ Error creating local quote: {e}")
            traceback.print_exc()

    def _create_task_from_quote(self, quote: Dict[str, Any]) -> Optional[Task]:
        """Create a work task from a quote."""
        try:
            with self._database.connection() as conn:
                columns = conn.execute("PRAGMA table_info(quotes)").fetchall()
                has_task_id = any(col[1] == 'task_id' for col in columns)
                
                if has_task_id:
                    existing = conn.execute(
                        "SELECT task_id FROM quotes WHERE reference = ? AND task_id IS NOT NULL",
                        (quote.get("reference"),)
                    ).fetchone()
                    if existing and existing["task_id"]:
                        print(f"ℹ️ Quote {quote.get('reference')} already has task ID: {existing['task_id']}")
                        return self._work_service.get_work(existing["task_id"])
            
            items = quote.get('items', [])
            item_names = [item.get('name', '') for item in items[:5]]
            item_summary = ', '.join(item_names) if item_names else 'No items specified'
            if len(items) > 5:
                item_summary += f' and {len(items) - 5} more'

            customer_name = quote.get("customerName") or quote.get("customer_name", "Unknown")
            reference = quote.get("reference", "N/A")
            
            from datetime import date
            today = date.today().isoformat()
            
            description = f"""Quote: {reference}
Customer: {customer_name}
Email: {quote.get('email', 'N/A')}
Phone: {quote.get('phone', 'N/A')}

Items Requested:
{item_summary}

Notes: {quote.get('notes', 'No notes')}"""
            
            task = Task(
                id=None,
                title=f"Quote: {reference} - {customer_name}",
                description=description,
                assigned_employee="",
                assigned_by="System (Quote Sync)",
                priority="Medium",
                status="New",
                department="Operations",
                created_date=today,
                start_date="",
                due_date="",
                estimated_hours=0,
                category="RFQ",
                actual_hours=0,
                comments=f'Quote from website. Reference: {reference}',
                checklist="[]",
                attachments="[]",
            )
            
            saved_task = self._work_service.create_work(task)
            print(f"✅ Created task ID {saved_task.id} for quote {reference}")

            with self._database.connection() as conn:
                columns = conn.execute("PRAGMA table_info(quotes)").fetchall()
                has_task_id = any(col[1] == 'task_id' for col in columns)
                if has_task_id:
                    conn.execute(
                        "UPDATE quotes SET task_id = ? WHERE reference = ?",
                        (saved_task.id, reference)
                    )
                    conn.commit()

            return saved_task
        except Exception as e:
            print(f"❌ Error creating task from quote: {e}")
            traceback.print_exc()
            return None

    def get_quote_statistics(self) -> Dict[str, Any]:
        """Get statistics about quotes."""
        try:
            with self._database.connection() as conn:
                table_exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='quotes'"
                ).fetchone()
                
                if not table_exists:
                    return {"total": 0, "by_status": {}, "tasks_created": 0}
                
                total = conn.execute("SELECT COUNT(*) as count FROM quotes").fetchone()["count"]
                
                by_status = {}
                for status in ["Pending", "In Review", "Quoted", "Closed"]:
                    count = conn.execute(
                        "SELECT COUNT(*) as count FROM quotes WHERE status = ?",
                        (status,)
                    ).fetchone()["count"]
                    by_status[status] = count
                
                columns = conn.execute("PRAGMA table_info(quotes)").fetchall()
                has_task_id = any(col[1] == 'task_id' for col in columns)
                tasks_created = 0
                if has_task_id:
                    tasks_created = conn.execute(
                        "SELECT COUNT(*) as count FROM quotes WHERE task_id IS NOT NULL"
                    ).fetchone()["count"]
                
                return {
                    "total": total,
                    "by_status": by_status,
                    "tasks_created": tasks_created
                }
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {"total": 0, "by_status": {}, "tasks_created": 0}

    def sync_quote_to_mongodb(self, reference: str) -> Dict[str, Any]:
        """Push a local quote update to MongoDB."""
        try:
            local_quote = self.get_local_quote(reference)
            if not local_quote:
                return {"success": False, "message": f"Quote {reference} not found locally"}

            update_data = {
                'status': self._map_status_to_mongo(local_quote.get('status', 'Pending')),
                'updatedAt': datetime.now().isoformat()
            }
            
            if local_quote.get('reply_message'):
                update_data['replyMessage'] = local_quote['reply_message']
                update_data['repliedAt'] = datetime.now().isoformat()
            
            if local_quote.get('assigned_to'):
                update_data['assignedTo'] = local_quote['assigned_to']
                update_data['assignedAt'] = datetime.now().isoformat()
            
            result = self._mongodb._db.quotes.update_one(
                {'reference': reference.upper()},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                self._update_sync_timestamp(reference)
                return {"success": True, "message": f"Updated {reference} in MongoDB"}
            else:
                return {"success": False, "message": "No changes to sync"}
                
        except Exception as e:
            print(f"❌ Error syncing to MongoDB: {e}")
            return {"success": False, "message": str(e)}

    def sync_all_to_mongodb(self) -> Dict[str, Any]:
        """Push all local quotes that have changes to MongoDB."""
        try:
            with self._database.connection() as conn:
                columns = conn.execute("PRAGMA table_info(quotes)").fetchall()
                has_last_sync = any(col[1] == 'last_sync_at' for col in columns)
                
                if has_last_sync:
                    rows = conn.execute("""
                        SELECT * FROM quotes 
                        WHERE last_sync_at IS NULL 
                        OR updated_at > last_sync_at
                    """).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM quotes").fetchall()
                
                synced_count = 0
                for row in rows:
                    result = self.sync_quote_to_mongodb(row["reference"])
                    if result["success"]:
                        synced_count += 1
                
                return {
                    "success": True,
                    "message": f"Synced {synced_count} quotes to MongoDB",
                    "synced": synced_count
                }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _get_local_quote(self, reference: str) -> Optional[Dict[str, Any]]:
        try:
            with self._database.connection() as conn:
                row = conn.execute(
                    "SELECT reference, updated_at FROM quotes WHERE reference = ?",
                    (reference,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error checking local quote: {e}")
            return None

    def get_local_quote(self, reference: str) -> Optional[Dict[str, Any]]:
        try:
            with self._database.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM quotes WHERE reference = ?",
                    (reference,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error getting quote: {e}")
            return None

    def _update_local_quote(self, existing: Dict[str, Any], quote: Dict[str, Any]) -> None:
        try:
            items = quote.get("items", [])
            if isinstance(items, list):
                cleaned_items = []
                for item in items:
                    if isinstance(item, dict):
                        cleaned_item = {}
                        for k, v in item.items():
                            if k != '_id':
                                cleaned_item[k] = v
                        cleaned_items.append(cleaned_item)
                    else:
                        cleaned_items.append(item)
                items_json = json.dumps(cleaned_items)
            else:
                items_json = json.dumps([])
                
            with self._database.connection() as conn:
                conn.execute(
                    """
                    UPDATE quotes 
                    SET status = ?, notes = ?, items = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE reference = ?
                    """,
                    (
                        self._map_status_to_local(quote.get("status", "received")),
                        quote.get("notes", ""),
                        items_json,
                        quote.get("reference")
                    )
                )
                conn.commit()
        except Exception as e:
            print(f"Error updating local quote: {e}")

    def _update_sync_timestamp(self, reference: str) -> None:
        try:
            with self._database.connection() as conn:
                columns = conn.execute("PRAGMA table_info(quotes)").fetchall()
                has_last_sync = any(col[1] == 'last_sync_at' for col in columns)
                
                if has_last_sync:
                    conn.execute(
                        "UPDATE quotes SET last_sync_at = CURRENT_TIMESTAMP WHERE reference = ?",
                        (reference,)
                    )
                    conn.commit()
        except Exception:
            pass

    def _needs_update(self, existing: Dict[str, Any], new: Dict[str, Any]) -> bool:
        existing_status = self._map_status_to_local(existing.get("status", ""))
        new_status = self._map_status_to_local(new.get("status", ""))
        return existing_status != new_status

    @staticmethod
    def _map_status_to_local(mongo_status: str) -> str:
        if not mongo_status:
            return "Pending"
        status_map = {
            "received": "Pending",
            "in_review": "In Review",
            "in review": "In Review",
            "quoted": "Quoted",
            "closed": "Closed"
        }
        return status_map.get(str(mongo_status).lower(), "Pending")

    @staticmethod
    def _map_status_to_mongo(local_status: str) -> str:
        status_map = {
            "Pending": "received",
            "In Review": "in_review",
            "Quoted": "quoted",
            "Closed": "closed"
        }
        return status_map.get(local_status, "received")

    def sync_quotes(self) -> List[Dict[str, Any]]:
        """
        Compatibility method used by the application timer.

        It synchronizes quotes from MongoDB into SQLite and returns
        the list of synchronized quotes.
        """
        try:
            result = self.sync_quotes_from_mongodb()

            if not result.get("success"):
                return []

            # Return quotes for any UI that expects a list
            return self._mongodb.get_quotes(limit=200)

        except Exception as e:
            print(f"⚠️ Quote sync error: {e}")
            return []