import crypto from 'node:crypto';
import mongoose from 'mongoose';

let desktopDb: any = null;

function todaySouthAfrica(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Johannesburg',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

function hashPbkdf2Sha256(password: string): string {
  const iterations = 310_000;
  const salt = crypto.randomBytes(16).toString('hex');
  const digest = crypto.pbkdf2Sync(Buffer.from(password, 'utf8'), Buffer.from(salt, 'utf8'), iterations, 32, 'sha256').toString('hex');
  return `pbkdf2_sha256$${iterations}$${salt}$${digest}`;
}

function valuesEqual(a: any, b: any): boolean {
  return String(a) === String(b);
}

function getPath(source: any, path: string): any {
  return String(path).split('.').reduce((value, key) => value == null ? undefined : value[key], source);
}

function setPath(source: any, path: string, value: any): void {
  const keys = String(path).split('.');
  let cursor = source;
  for (const key of keys.slice(0, -1)) {
    if (!cursor[key] || typeof cursor[key] !== 'object') cursor[key] = {};
    cursor = cursor[key];
  }
  cursor[keys[keys.length - 1]] = value;
}

function unsetPath(source: any, path: string): void {
  const keys = String(path).split('.');
  let cursor = source;
  for (const key of keys.slice(0, -1)) {
    if (!cursor[key] || typeof cursor[key] !== 'object') return;
    cursor = cursor[key];
  }
  delete cursor[keys[keys.length - 1]];
}

function matchesCondition(actual: any, expected: any): boolean {
  if (expected && typeof expected === 'object' && !(expected instanceof Date) && !(expected instanceof mongoose.Types.ObjectId)) {
    for (const [op, value] of Object.entries(expected)) {
      if (op === '$in' && !(Array.isArray(value) && value.some(item => valuesEqual(actual, item)))) return false;
      if (op === '$nin' && Array.isArray(value) && value.some(item => valuesEqual(actual, item))) return false;
      if (op === '$ne' && valuesEqual(actual, value)) return false;
      if (op === '$exists' && ((actual !== undefined) !== Boolean(value))) return false;
      if (op === '$gte' && !(String(actual || '') >= String(value))) return false;
      if (op === '$lte' && !(String(actual || '') <= String(value))) return false;
      if (op === '$gt' && !(String(actual || '') > String(value))) return false;
      if (op === '$lt' && !(String(actual || '') < String(value))) return false;
      if (op === '$regex') {
        const flags = String((expected as any).$options || '');
        if (!new RegExp(String(value), flags).test(String(actual || ''))) return false;
      }
    }
    return true;
  }
  return valuesEqual(actual, expected);
}

function matchesQuery(doc: any, query: any = {}): boolean {
  for (const [key, expected] of Object.entries(query || {})) {
    if (key === '$or') {
      if (!(Array.isArray(expected) && expected.some(item => matchesQuery(doc, item)))) return false;
      continue;
    }
    if (key === '$and') {
      if (!(Array.isArray(expected) && expected.every(item => matchesQuery(doc, item)))) return false;
      continue;
    }
    if (!matchesCondition(getPath(doc, key), expected)) return false;
  }
  return true;
}

function applyProjection(doc: any, projection: any): any {
  if (!projection) return doc;
  const clone = { ...doc };
  for (const [key, value] of Object.entries(projection)) {
    if (value === 0) unsetPath(clone, key);
  }
  return clone;
}

function sortRows(rows: any[], sort: any): any[] {
  if (!sort) return rows;
  return [...rows].sort((a, b) => {
    for (const [key, direction] of Object.entries(sort)) {
      const av = getPath(a, key);
      const bv = getPath(b, key);
      if (valuesEqual(av, bv)) continue;
      const result = String(av || '').localeCompare(String(bv || ''));
      return Number(direction) < 0 ? -result : result;
    }
    return 0;
  });
}

function cursor(rows: any[]) {
  let current = [...rows];
  let projection: any = null;
  return {
    sort(sort: any) {
      current = sortRows(current, sort);
      return this;
    },
    limit(limit: number) {
      current = current.slice(0, Number(limit || current.length));
      return this;
    },
    project(project: any) {
      projection = project;
      return this;
    },
    async toArray() {
      return current.map(row => applyProjection(row, projection));
    },
  };
}

function collection(rows: any[]) {
  return {
    async findOne(query: any = {}, options: any = {}) {
      const found = rows.find(row => matchesQuery(row, query));
      return found ? applyProjection(found, options?.projection) : null;
    },
    find(query: any = {}) {
      return cursor(rows.filter(row => matchesQuery(row, query)));
    },
    async countDocuments(query: any = {}) {
      return rows.filter(row => matchesQuery(row, query)).length;
    },
    async insertOne(doc: any) {
      const _id = doc._id || new mongoose.Types.ObjectId();
      rows.push({ ...doc, _id });
      return { insertedId: _id };
    },
    async updateOne(query: any, update: any) {
      const found = rows.find(row => matchesQuery(row, query));
      if (!found) return { matchedCount: 0, modifiedCount: 0 };
      if (update.$set) for (const [key, value] of Object.entries(update.$set)) setPath(found, key, value);
      if (update.$unset) for (const key of Object.keys(update.$unset)) unsetPath(found, key);
      if (update.$inc) {
        for (const [key, value] of Object.entries(update.$inc)) {
          setPath(found, key, Number(getPath(found, key) || 0) + Number(value || 0));
        }
      }
      if (update.$push) {
        for (const [key, value] of Object.entries(update.$push)) {
          const existing = getPath(found, key);
          if (Array.isArray(existing)) existing.push(value);
          else setPath(found, key, [value]);
        }
      }
      return { matchedCount: 1, modifiedCount: 1 };
    },
    async deleteOne(query: any) {
      const index = rows.findIndex(row => matchesQuery(row, query));
      if (index < 0) return { deletedCount: 0 };
      rows.splice(index, 1);
      return { deletedCount: 1 };
    },
    async findOneAndUpdate(query: any, update: any, options: any = {}) {
      let found = rows.find(row => matchesQuery(row, query));
      if (!found && options.upsert) {
        found = { ...query, _id: query._id || new mongoose.Types.ObjectId() };
        rows.push(found);
      }
      if (found) await this.updateOne({ _id: found._id }, update);
      return { value: found };
    },
    aggregate(pipeline: any[] = []) {
      let current = [...rows];
      for (const stage of pipeline) {
        if (stage.$match) current = current.filter(row => matchesQuery(row, stage.$match));
        if (stage.$group) {
          const grouped = new Map<string, any>();
          for (const row of current) {
            const idField = String(stage.$group._id || '').replace(/^\$/, '');
            const id = getPath(row, idField);
            const key = String(id || '');
            if (!grouped.has(key)) grouped.set(key, { _id: id });
            const target = grouped.get(key);
            for (const [field, expression] of Object.entries(stage.$group)) {
              if (field === '_id') continue;
              const expr: any = expression;
              if (expr?.$sum === 1) target[field] = Number(target[field] || 0) + 1;
              else if (expr?.$sum?.$ifNull) {
                const source = String(expr.$sum.$ifNull[0]).replace(/^\$/, '');
                target[field] = Number(target[field] || 0) + Number(getPath(row, source) || expr.$sum.$ifNull[1] || 0);
              } else if (expr?.$sum?.$cond) {
                target[field] = Number(target[field] || 0);
              }
            }
          }
          current = Array.from(grouped.values());
        }
        if (stage.$sort) current = sortRows(current, stage.$sort);
        if (stage.$limit) current = current.slice(0, Number(stage.$limit));
      }
      return cursor(current);
    },
  };
}

export function ensureInMemoryDesktopDb() {
  if (desktopDb) return desktopDb;
  const now = new Date();
  const directorId = new mongoose.Types.ObjectId();
  const opsId = new mongoose.Types.ObjectId();
  const staffId = new mongoose.Types.ObjectId();
  const rows: Record<string, any[]> = {
    users: [
      { _id: directorId, employee_id: directorId, username: 'director@untangledits.co.za', email: 'director@untangledits.co.za', full_name: 'Demo Director', role: 'Director', status: 'active', password_hash: hashPbkdf2Sha256('NexusDemo2026!'), created_at: now, updated_at: now },
      { _id: opsId, employee_id: opsId, username: 'operations@untangledits.co.za', email: 'operations@untangledits.co.za', full_name: 'Demo Operations Manager', role: 'Operations Manager', status: 'active', password_hash: hashPbkdf2Sha256('NexusDemo2026!'), created_at: now, updated_at: now },
      { _id: staffId, employee_id: staffId, username: 'staff@untangledits.co.za', email: 'staff@untangledits.co.za', full_name: 'Demo Staff Member', role: 'Staff', status: 'active', password_hash: hashPbkdf2Sha256('NexusDemo2026!'), created_at: now, updated_at: now },
    ],
    employees: [
      { _id: directorId, employee_id: directorId, full_name: 'Demo Director', email: 'director@untangledits.co.za', department: 'Executive', position: 'Director', role: 'Director', status: 'Active' },
      { _id: opsId, employee_id: opsId, full_name: 'Demo Operations Manager', email: 'operations@untangledits.co.za', department: 'Operations', position: 'Operations Manager', role: 'Operations Manager', status: 'Active' },
      { _id: staffId, employee_id: staffId, full_name: 'Demo Staff Member', email: 'staff@untangledits.co.za', department: 'Operations', position: 'Technician', role: 'Staff', status: 'Active' },
    ],
    api_sessions: [],
    counters: [{ _id: 'work_assignments', seq: 4 }],
    work_assignments: [
      { _id: new mongoose.Types.ObjectId(), task_number: 'TASK-00001', title: 'Review supplier registration pack', description: 'Check documents and assign next step.', category: 'Supplier Registration', department: 'Operations', priority: 'High', status: 'Dumped', assigned_employee: '', assigned_employee_id: null, assigned_by: '', dumped_by: 'Demo Director', due_date: todaySouthAfrica(), start_date: '', estimated_hours: 2, actual_hours: 0, created_at: now, updated_at: now, history: [] },
      { _id: new mongoose.Types.ObjectId(), task_number: 'TASK-00002', title: 'Prepare weekly director summary', description: 'Summarise approvals, workload, and open risks.', category: 'Administration', department: 'Executive', priority: 'Critical', status: 'Assigned', assigned_employee: 'Demo Operations Manager', assigned_employee_id: opsId, assigned_by: 'Demo Director', dumped_by: 'Demo Director', due_date: todaySouthAfrica(), start_date: todaySouthAfrica(), estimated_hours: 3, actual_hours: 1.25, created_at: now, updated_at: now, history: [] },
      { _id: new mongoose.Types.ObjectId(), task_number: 'TASK-00003', title: 'Install workstation for new hire', description: 'Set up laptop, email, and required software.', category: 'Technical', department: 'Operations', priority: 'Medium', status: 'In Progress', assigned_employee: 'Demo Staff Member', assigned_employee_id: staffId, assigned_by: 'Demo Operations Manager', dumped_by: 'Demo Operations Manager', due_date: todaySouthAfrica(), start_date: todaySouthAfrica(), estimated_hours: 4, actual_hours: 2, active_timer_started_at: now, created_at: now, updated_at: now, history: [] },
    ],
    approvals: [],
    hr_leave_requests: [
      { _id: new mongoose.Types.ObjectId(), title: 'Sick Leave: Demo Staff Member', request_type: 'Sick Leave', employee_id: staffId, employee_name: 'Demo Staff Member', department: 'Operations', start_date: todaySouthAfrica(), end_date: todaySouthAfrica(), reason: 'Doctor booked employee off sick.', status: 'Pending', current_stage: 'Operations Manager', sick_note: { file_name: 'demo-sick-note.pdf', file_type: 'application/pdf', file_size: 24576, status: 'Pending Evaluation' }, created_at: now, updated_at: now, history: [] },
    ],
    calendar_events: [],
    attendance: [],
  };

  desktopDb = {
    collection(name: string) {
      if (!rows[name]) rows[name] = [];
      return collection(rows[name]);
    },
  };
  console.log('🔐 Local demo credentials enabled: director@untangledits.co.za / NexusDemo2026!');
  return desktopDb;
}
