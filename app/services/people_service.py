"""People module data service using MongoDB users collection."""

from typing import Any

from app.models.employee import Employee
from app.services.mongodb_service import MongoDBService


class PeopleService:
    """
    Provides employee/people data from MongoDB.

    IMPORTANT:
    The users collection is the source of truth for people records.

    Authentication fields such as password_hash are NEVER exposed
    through this service.
    """

    PROFILE_DEFAULTS = {
        "siyanda nkosi": {
            "position": "Senior Full-Stack Developer", "team": "Website & Commerce",
            "skills": "React, Python, REST APIs, GitHub, E-commerce",
        },
        "nonhlanhla hlatshwayo": {
            "position": "QA & Operations Analyst", "team": "Nexus Delivery",
            "skills": "UAT, Quality Assurance, Python, Documentation, Sprint Planning",
        },
        "ubuntu hadebe": {
            "position": "Operations Manager", "team": "Operations & Delivery",
            "skills": "Operations, Sprint Planning, Project Coordination, Approvals, Reporting",
        },
        "gift wesi": {
            "position": "Hardware Refurbishment Technician", "team": "Technical Services",
            "skills": "Laptop Repair, Diagnostics, Hardware Upgrades, Windows, Device Testing",
        },
        "dipuo tlowana": {
            "position": "RFQ & Tender Coordinator", "team": "Commercial Operations",
            "skills": "RFQ, Tender Compliance, Supplier Pricing, Procurement, Quality Checks",
        },
        "bongiwe ngobese": {
            "position": "Digital Marketing Specialist", "team": "Marketing & Sales",
            "skills": "Content Marketing, Social Media, Campaigns, Product Listings, Analytics",
        },
        "botshelo lehasa": {
            "position": "Client Support Coordinator", "team": "Client Services",
            "skills": "Client Support, Ticketing, Order Follow-up, Administration, Escalations",
        },
    }

    def __init__(self, mongodb: MongoDBService) -> None:
        self._mongodb = mongodb

    # ==================================================================
    # DATABASE
    # ==================================================================

    @property
    def db_name(self) -> str:
        """Return the MongoDB database name."""
        return self._mongodb.db_name

    @property
    def collection(self) -> Any:
        """
        Return the MongoDB users collection.

        Employee/people information is stored in users in the current
        Untangled Nexus database.
        """
        return self._mongodb.get_collection("users")

    # ==================================================================
    # EMPLOYEES / PEOPLE
    # ==================================================================

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> list[Employee]:
        """
        Return all people from MongoDB users collection.

        Optional filters:
            search
            department
            role
            status
        """

        query: dict[str, Any] = {}

        # --------------------------------------------------------------
        # Search
        # --------------------------------------------------------------

        if search:
            search_pattern = {
                "$regex": search,
                "$options": "i",
            }

            query["$or"] = [
                {"full_name": search_pattern},
                {"first_name": search_pattern},
                {"last_name": search_pattern},
                {"position": search_pattern},
                {"email": search_pattern},
                {"username": search_pattern},
                {"employee_number": search_pattern},
                {"employee_id": search_pattern},
                {"department": search_pattern},
                {"role": search_pattern},
                {"status": search_pattern},
                {"skills": search_pattern},
                {"team": search_pattern},
            ]

        # --------------------------------------------------------------
        # Department
        # --------------------------------------------------------------

        if department and department != "All":
            query["department"] = department

        # --------------------------------------------------------------
        # Role
        # --------------------------------------------------------------

        if role and role != "All":
            query["role"] = role

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        if status and status != "All":

            # Users collection uses "active" in your current data.
            #
            # The UI may use "Active", so support both.
            if str(status).lower() == "active":
                query["status"] = {
                    "$in": [
                        "active",
                        "Active",
                    ]
                }

            elif str(status).lower() == "inactive":
                query["status"] = {
                    "$in": [
                        "inactive",
                        "Inactive",
                    ]
                }

            else:
                query["status"] = status

        # --------------------------------------------------------------
        # MongoDB query
        # --------------------------------------------------------------

        documents = list(
            self.collection.find(query).sort(
                [
                    ("full_name", 1),
                    ("username", 1),
                ]
            )
        )

        print(
            f"👥 PeopleService: MongoDB users query returned "
            f"{len(documents)} people"
        )

        return [
            self._document_to_employee(document)
            for document in documents
        ]

    # ==================================================================
    # SINGLE EMPLOYEE
    # ==================================================================

    def get_employee(
        self,
        employee_id: int | str,
    ) -> Employee | None:
        """
        Return one person from MongoDB users.

        Supports:

        - MongoDB ObjectId
        - numeric employee_id
        - string employee_id
        - username
        - email
        """

        document = None

        # --------------------------------------------------------------
        # Try MongoDB ObjectId
        # --------------------------------------------------------------

        try:

            from bson import ObjectId

            if isinstance(employee_id, ObjectId):

                document = self.collection.find_one(
                    {
                        "_id": employee_id
                    }
                )

            elif isinstance(employee_id, str):

                if ObjectId.is_valid(employee_id):

                    document = self.collection.find_one(
                        {
                            "_id": ObjectId(employee_id)
                        }
                    )

        except Exception:
            document = None

        # --------------------------------------------------------------
        # Try numeric employee_id
        # --------------------------------------------------------------

        if document is None:

            try:

                numeric_id = int(employee_id)

                document = self.collection.find_one(
                    {
                        "employee_id": numeric_id
                    }
                )

            except (TypeError, ValueError):
                pass

        # --------------------------------------------------------------
        # Try employee_id as string
        # --------------------------------------------------------------

        if document is None and isinstance(
            employee_id,
            str,
        ):

            document = self.collection.find_one(
                {
                    "employee_id": employee_id
                }
            )

        # --------------------------------------------------------------
        # Try username
        # --------------------------------------------------------------

        if document is None and isinstance(
            employee_id,
            str,
        ):

            document = self.collection.find_one(
                {
                    "username": employee_id
                }
            )

        # --------------------------------------------------------------
        # Try email
        # --------------------------------------------------------------

        if document is None and isinstance(
            employee_id,
            str,
        ):

            document = self.collection.find_one(
                {
                    "email": employee_id
                }
            )

        # --------------------------------------------------------------
        # Not found
        # --------------------------------------------------------------

        if document is None:
            return None

        return self._document_to_employee(document)

    # ==================================================================
    # FIND BY NAME
    # ==================================================================

    def get_employee_by_name(
        self,
        full_name: str,
    ) -> Employee | None:
        """Return a person by display name."""

        if not full_name:
            return None

        document = self.collection.find_one(
            {
                "full_name": full_name
            }
        )

        if document is None:
            return None

        return self._document_to_employee(document)

    # ==================================================================
    # FILTER VALUES
    # ==================================================================

    def get_departments(self) -> list[str]:
        """Return unique departments from users."""

        return self._distinct_values(
            "department"
        )

    def get_roles(self) -> list[str]:
        """Return unique roles from users."""

        return self._distinct_values(
            "role"
        )

    def get_statuses(self) -> list[str]:
        """Return unique statuses from users."""

        return self._distinct_values(
            "status"
        )

    def get_employee_names(self) -> list[str]:
        """Return employee names sorted alphabetically."""

        values = self.collection.distinct(
            "full_name"
        )

        return sorted(
            [
                str(value)
                for value in values
                if value is not None
                and str(value).strip()
            ],
            key=str.lower,
        )

    def _distinct_values(
        self,
        field_name: str,
    ) -> list[str]:
        """Return unique non-empty values."""

        values = self.collection.distinct(
            field_name
        )

        return sorted(
            [
                str(value)
                for value in values
                if value is not None
                and str(value).strip()
            ],
            key=str.lower,
        )

    # ==================================================================
    # MONGODB USER -> EMPLOYEE MODEL
    # ==================================================================

    @staticmethod
    def _document_to_employee(
        document: dict[str, Any],
    ) -> Employee:
        """
        Convert a MongoDB users document to Employee model.

        IMPORTANT:
        password_hash and other authentication-only fields are
        intentionally ignored.
        """

        # --------------------------------------------------------------
        # ID
        # --------------------------------------------------------------

        employee_id: int | str | None = None

        raw_employee_id = document.get(
            "employee_id"
        )

        if isinstance(
            raw_employee_id,
            int,
        ):

            employee_id = raw_employee_id

        elif isinstance(
            raw_employee_id,
            float,
        ):

            employee_id = int(
                raw_employee_id
            )

        elif isinstance(
            document.get("id"),
            int,
        ):

            employee_id = document["id"]

        elif isinstance(
            document.get("sqlite_id"),
            int,
        ):

            employee_id = document[
                "sqlite_id"
            ]

        elif document.get("_id") is not None:

            employee_id = str(document["_id"])

        # --------------------------------------------------------------
        # Safe text helper
        # --------------------------------------------------------------

        def text(
            field: str,
            default: str = "",
        ) -> str:

            value = document.get(
                field,
                default,
            )

            if value is None:
                return default

            return str(value)

        # --------------------------------------------------------------
        # Safe boolean helper
        # --------------------------------------------------------------

        def boolean(
            field: str,
            default: bool = False,
        ) -> bool:

            value = document.get(
                field,
                default,
            )

            if isinstance(
                value,
                bool,
            ):
                return value

            if isinstance(
                value,
                str,
            ):

                return (
                    value.strip().lower()
                    in {
                        "true",
                        "1",
                        "yes",
                        "y",
                        "active",
                    }
                )

            if isinstance(
                value,
                (int, float),
            ):

                return bool(value)

            return default

        # --------------------------------------------------------------
        # Safe number helper
        # --------------------------------------------------------------

        def number(
            field: str,
            default: float = 0.0,
        ) -> float:

            value = document.get(
                field,
                default,
            )

            try:

                return float(
                    value or default
                )

            except (
                TypeError,
                ValueError,
            ):

                return default

        # --------------------------------------------------------------
        # Name handling
        # --------------------------------------------------------------

        first_name = text(
            "first_name"
        )

        last_name = text(
            "last_name"
        )

        full_name = text(
            "full_name"
        )

        if not full_name:

            full_name = " ".join(
                part
                for part in [
                    first_name,
                    last_name,
                ]
                if part
            )

        defaults = PeopleService.PROFILE_DEFAULTS.get(full_name.strip().casefold(), {})
        username = text("username") or text("email").split("@")[0]
        if not username:
            username = ".".join(full_name.lower().split())
        clocked_in = boolean("clocked_in", False)
        raw_presence = text("presence", text("availability", "")).strip().lower()
        if raw_presence in {"online", "active", "available"}:
            presence = "online"
        elif raw_presence in {"away", "idle", "on break", "on_break"}:
            presence = "away"
        elif raw_presence in {"do_not_disturb", "do not disturb", "dnd", "busy"}:
            presence = "dnd"
        else:
            presence = "online" if clocked_in else "offline"
        position = (
            text("position") or text("job_title")
            or str(defaults.get("position", "Team Member"))
        )
        skills = text("skills") or str(defaults.get("skills", ""))
        team = text("team") or str(defaults.get("team", "")) or text("department")

        # --------------------------------------------------------------
        # Employee number
        # --------------------------------------------------------------

        employee_number = text(
            "employee_number"
        )

        if not employee_number:

            employee_number = text(
                "employee_id"
            )

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        status = text(
            "status"
        )

        if not status:

            status = "active"

        # --------------------------------------------------------------
        # Date joined
        # --------------------------------------------------------------

        date_joined = text(
            "date_joined"
        )

        if not date_joined:

            date_joined = text(
                "created_at"
            )

        # --------------------------------------------------------------
        # Create Employee model
        # --------------------------------------------------------------

        return Employee(

            id=employee_id,

            employee_number=employee_number,

            first_name=first_name,

            last_name=last_name,

            full_name=full_name,

            position=position,

            department=text(
                "department"
            ),

            role=text(
                "role",
                "Staff",
            ),

            reports_to=text(
                "reports_to"
            ),

            mentor=text(
                "mentor"
            ),

            email=text(
                "email"
            ),

            phone=text(
                "phone",
                text(
                    "phone_number",
                    "",
                ),
            ),

            status=status,

            employment_type=text(
                "employment_type"
            ),

            date_joined=date_joined,

            clocked_in=clocked_in,

            current_task=text(
                "current_task",
                "No active task",
            ),

            profile_photo=text(
                "profile_photo"
            ),

            skills=skills,

            permissions=text(
                "permissions"
            ),

            performance_score=number(
                "performance_score",
                0.0,
            ),

            training_progress=number(
                "training_progress",
                0.0,
            ),

            notes=text(
                "notes"
            ),

            username=username,

            team=team,

            slack_handle=text("slack_handle", f"@{username}"),

            timezone=text("timezone", "Africa/Johannesburg (SAST)"),

            presence=presence,
        )
