"""Real Tk event-loop checks; no production endpoints or credentials."""
import importlib
import threading
import time
from types import SimpleNamespace
import pytest
import customtkinter as ctk
from app.utils.ui_tasks import ui_task, RemoteCall, ui_steps, action_steps
from app.utils.async_tasks import run_in_background

@pytest.fixture(scope='module')
def tk_root():
    window=ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()

@pytest.fixture
def root(monkeypatch,tk_root):
    root=tk_root
    from app.utils.async_tasks import start_ui_dispatcher
    start_ui_dispatcher(root)
    failures = []
    root.report_callback_exception = lambda *error: failures.append(error)
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: failures.append(a))
    root.test_failures = failures
    yield root
    for child in root.winfo_children():
        child.destroy()
    for job in root.tk.call('after','info'):
        root.after_cancel(job)
    root._nexus_dispatcher_started=False
    assert not failures, failures


def pump(root, done, timeout=10):
    end = time.monotonic() + timeout
    while not done():
        root.update()
        if time.monotonic() > end:
            pytest.fail('UI operation did not finish')
        time.sleep(.005)
    root.update()


def test_four_second_response_keeps_tk_responsive_and_deduplicates(root):
    main = threading.get_ident()
    ticks = []
    calls = []
    def heartbeat():
        ticks.append(time.monotonic())
        root.after(25, heartbeat)
    heartbeat()
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from app.services.backend_api_client import BackendAPIClient
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(4)
            body=b'{"success":true}'
            self.send_response(200)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self,*args):
            pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    client=BackendAPIClient(base_url=f'http://127.0.0.1:{server.server_port}',timeout=6)
    def delayed(value):
        assert threading.get_ident() != main
        calls.append(value)
        assert client.request('GET','/delayed')['success']
        return value
    class View(ctk.CTkFrame):
        @ui_task
        def load(self):
            value = yield RemoteCall(delayed, self.entry.get())
            assert threading.get_ident() == main
            self.result = value
    view = View(root)
    view.entry = ctk.CTkEntry(view)
    view.entry.insert(0, 'captured on Tk')
    started = time.monotonic()
    view.load()
    view.load()
    assert time.monotonic() - started < .5
    pump(root, lambda: hasattr(view, 'result'))
    server.shutdown()
    server.server_close()
    assert calls == ['captured on Tk']
    assert len(ticks) > 80
    assert max(b-a for a,b in zip(ticks,ticks[1:])) < .5


def test_destroyed_owner_discards_callback(root):
    view = ctk.CTkFrame(root)
    complete = threading.Event()
    deliveries = []
    def operation():
        complete.wait(2)
        return 7
    worker=run_in_background(view,operation,deliveries.append)
    view.destroy()
    complete.set()
    pump(root, lambda: not worker.is_alive())
    until=time.monotonic()+.15
    pump(root, lambda: time.monotonic()>until)
    assert deliveries == []


def test_errors_resume_on_tk_and_allow_retry(root):
    main=threading.get_ident()
    class View(ctk.CTkFrame):
        @ui_task
        def load(self):
            try:
                yield RemoteCall(lambda: (_ for _ in ()).throw(TimeoutError('Timed out')))
            except TimeoutError:
                assert threading.get_ident()==main
                self.errors=getattr(self,'errors',0)+1
    view=View(root)
    view.load()
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    view.load()
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    assert view.errors==2


@pytest.fixture
def controllers(monkeypatch):
    from app.services.backend_api_client import BackendAPIClient
    from app.services.backend_auth_service import BackendAuthService
    from app.services.auth_service import AuthService
    from app.services.people_service import PeopleService
    from app.services.dashboard_service import DashboardService
    from app.services.attendance_service import AttendanceService
    from app.services.work_service import WorkService
    from app.controllers.app_controller import AppController
    main=threading.get_ident()
    calls=[]
    violations=[]
    def request(self,method,path,*args,**kwargs):
        if threading.get_ident()==main:
            violations.append(path)
        assert threading.get_ident()!=main, 'Network call on Tk: '+path
        calls.append(path)
        time.sleep(.02)
        if '/reports/types' in path:return {'types':['Task Workload']}
        if '/office-requests/items' in path:return {'items':['Mouse']}
        return {'success':True,'employees':[],'tasks':[],'users':[],'events':[],'notifications':[],'requests':[],'approvals':[],'projects':[],'rows':[],'records':[],'count':0}
    monkeypatch.setattr(BackendAPIClient,'request',request)
    backend=BackendAPIClient(base_url='http://test.invalid')
    session={'token':'test-only','user':{'id':'u1','employee_id':'e1','username':'test','full_name':'Test User','role':'Operations Manager'},'employee':{'id':'e1','employee_id':'e1','full_name':'Test User'}}
    backend.session_data=session;backend.token='test-only'
    auth_backend=BackendAuthService(backend)
    auth=AuthService(auth_backend);auth.set_session_from_mongo(session)
    people=PeopleService(backend)
    app=AppController(auth,auth_backend,people,DashboardService(backend),AttendanceService(backend),WorkService(backend),backend)
    app._current_account=auth.current_user
    yield app,calls
    assert not violations, violations


@pytest.mark.parametrize('module,viewname,controller',[
 ('people_view','PeopleView','_people_controller'),
 ('task_view','TaskView','_task_controller'),
 ('calendar_view','CalendarView','_calendar_controller'),
 ('approval_view','ApprovalView','_approval_controller'),
 ('office_request_view','OfficeRequestView','_office_request_controller'),
 ('notification_view','NotificationView','_notification_controller'),
 ('project_view','ProjectView','_project_controller'),
 ('report_view','ReportView','_report_controller'),
 ('user_management_view','UserManagementView','_user_management_controller'),
 ('settings_view','SettingsView','_settings_controller'),
])
def test_screen_initial_load_uses_workers(root,controllers,module,viewname,controller):
    app,calls=controllers
    cls=getattr(importlib.import_module('app.views.'+module),viewname)
    view=cls(root,getattr(app,controller))
    view.pack(fill='both',expand=True)
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    assert calls, 'Screen did not attempt to load its API data'
    view.destroy()


def test_attendance_supporting_data_uses_workers(root,controllers):
    from app.views.attendance_view import AttendanceView
    app,calls=controllers
    view=AttendanceView(root,app._attendance_controller,app._mongo_attendance,app._current_account)
    pump(root,lambda:any('history?days=31' in path for path in calls) and not view.__dict__.get('_nexus_ui_task'))
    assert any('attendance/status' in path for path in calls)
    view.destroy()


def test_dashboard_existing_worker(root,controllers):
    from app.views.dashboard_view import DashboardView
    app,calls=controllers
    view=DashboardView(root,app._dashboard_controller)
    pump(root,lambda:bool(calls) and not view._refresh_running)
    view.destroy()


def test_navigation_reuses_cached_workspace_view(controllers, monkeypatch):
    app, _ = controllers
    created = []

    class Window:
        workspace = object()

        def __init__(self):
            self.cache = {}

        def get_cached_workspace_view(self, destination):
            return self.cache.get(destination)

        def show_workspace_view(self, view, destination):
            self.cache[destination] = view
            return True

    window = Window()
    app._main_window = window

    def create_view(destination, workspace, controller):
        view = object()
        created.append((destination, view))
        return view

    app._navigation_controller = SimpleNamespace(get_view=create_view)

    assert app._navigate_destination("Projects") is True
    assert app._navigate_destination("Projects") is True
    assert len(created) == 1


def test_main_thread_network_guard(root):
    from app.services.backend_api_client import BackendAPIClient, BackendAPIError
    with pytest.raises(BackendAPIError,match='background worker'):
        BackendAPIClient(base_url='http://127.0.0.1:1').request('GET','/health')


def test_login_worker_and_success_callback_thread(root):
    from app.views.login_view import LoginView
    main=threading.get_ident()
    received=[]
    class Controller:
        requires_password_change = False

        def login(self,username,password,**kwargs):
            assert threading.get_ident()!=main
            time.sleep(.1)
            return True,''
        def complete_login(self):
            assert threading.get_ident()==main
            received.append('signed in')
    class Harness(ctk.CTkFrame):
        _submit=LoginView._submit
        _finish_login=LoginView._finish_login
        PRIMARY=PRIMARY_HOVER='#60920d'
        DISABLED='#888888'
        def withdraw(self):
            pass
        def _reset_login_button(self):
            self.login_button.configure(state='normal')
    view=Harness(root)
    view._controller=Controller();view._is_destroyed=False;view._login_success=False
    view.username_entry=ctk.CTkEntry(view);view.username_entry.insert(0,'test')
    view.password_entry=ctk.CTkEntry(view);view.password_entry.insert(0,'test-only')
    view.login_button=ctk.CTkButton(view);view._loading_label=ctk.CTkLabel(view);view.error_label=ctk.CTkLabel(view)
    view._submit();view._submit()
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    assert received==['signed in']
    view.destroy()


def test_session_expiry_queued_from_worker(root,controllers,monkeypatch):
    app,calls=controllers
    main=threading.get_ident();notified=[]
    app._main_window=root
    def logout():
        assert threading.get_ident()==main
        notified.append('logout')
    app._logout=logout
    monkeypatch.setattr('tkinter.messagebox.showwarning',lambda *a,**k:None)
    thread=threading.Thread(target=lambda:[app._queue_session_expired('test-only') for _ in range(2)])
    thread.start()
    pump(root,lambda:bool(notified))
    assert notified==['logout']
    app._queue_session_expired('old-session')
    end=time.monotonic()+.1
    pump(root,lambda:time.monotonic()>end)
    assert notified==['logout']


def test_task_action_captures_widgets_before_worker(root,controllers):
    from app.views.task_view import TaskView
    app,calls=controllers
    view=TaskView(root,app._task_controller)
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    main=threading.get_ident();work=[]
    entry=ctk.CTkEntry(view);entry.insert(0,'2')
    def operation(hours):
        assert threading.get_ident()!=main
        work.append(hours)
    action=lambda:(yield RemoteCall(operation,float(entry.get())))
    view._run('Log time',action)
    view._run('Log time',action)
    pump(root,lambda:not view.__dict__.get('_nexus_ui_task'))
    assert work==[2.0]
    view.destroy()


def test_task_header_actions_fit_workspace(root, controllers):
    from app.views.task_view import TaskView

    app, _calls = controllers
    view = TaskView(root, app._task_controller)
    view.configure(width=980, height=700)
    view.place(x=0, y=0)
    pump(root, lambda: not view.__dict__.get('_nexus_ui_task'))
    view.update_idletasks()

    assert view._pill_frame.grid_info()['row'] == 1
    assert view._pill_frame.winfo_width() <= view.winfo_width() - 48
    assert view._new_task_button.winfo_x() + view._new_task_button.winfo_width() <= view._new_task_button.master.winfo_width()
    view.destroy()


def test_user_management_compact_controls_reflow(root, controllers):
    from app.views.user_management_view import UserManagementView

    app, _calls = controllers
    view = UserManagementView(root, app._user_management_controller)
    view.configure(width=800, height=700)
    view.place(x=0, y=0)
    pump(root, lambda: not view.__dict__.get('_nexus_ui_task'))
    view.update_idletasks()
    view._compact = None
    view._apply_responsive_layout()

    assert view._compact is True
    assert view.search_entry.grid_info()['row'] == 1
    assert view.search_entry.grid_info()['columnspan'] == 2
    assert {(item.grid_info()['row'], item.grid_info()['column']) for item in view._stat_items} == {
        (1, 0), (1, 1), (2, 0), (2, 1),
    }
    view.destroy()


def test_quote_workspace_reflows_without_horizontal_overflow(root, controllers, monkeypatch):
    from app.views.quote_management_view import QuoteManagementView

    app, calls = controllers
    view = QuoteManagementView(
        root,
        auth_service=app._auth,
        navigation_controller=app._navigation_controller,
        backend_api=app._backend,
    )
    view.configure(width=980, height=700)
    view.place(x=0, y=0)
    pump(root, lambda: any(path == '/api/quotes' for path in calls))
    view.update_idletasks()
    monkeypatch.setattr(view, 'winfo_width', lambda: 980)
    view._compact_layout = None
    view._apply_responsive_layout()

    assert view._compact_layout is False
    assert view.grid_columnconfigure(0)['minsize'] + view.grid_columnconfigure(1)['minsize'] < view.winfo_width()
    assert view._status_filter_menu.grid_info()['sticky'] == 'ew'

    monkeypatch.setattr(view, 'winfo_width', lambda: 760)
    view.update_idletasks()
    view._compact_layout = None
    view._apply_responsive_layout()
    assert view._compact_layout is True
    assert view._list_panel.grid_info()['column'] == 0
    assert view._details_panel.grid_info()['column'] == 0
    assert view._details_panel.grid_info()['row'] == 1
    view.destroy()


def _password_dialog_owner(root):
    owner = ctk.CTkFrame(root)
    owner._bg = lambda: "#f3f6f0"
    owner._panel = lambda: "#ffffff"
    owner._text = lambda: "#16201a"
    owner._muted = lambda: "#6b776c"
    owner._font = lambda size, bold=False: ("Segoe UI", size)
    owner.ERROR = "#d64545"
    owner.DISABLED = "#8a958c"
    owner.PRIMARY = "#60920d"
    owner.PRIMARY_HOVER = "#74ae10"
    return owner


def test_mandatory_password_change_blocks_login_until_saved(root):
    from app.views.login_view import PasswordChangeDialog
    main = threading.get_ident()
    events = []

    class Controller:
        def change_password(self, current_password, new_password):
            assert threading.get_ident() != main
            events.append((current_password, new_password))
            time.sleep(.1)
            return True, ""

        def cancel_pending_login(self):
            assert threading.get_ident() != main
            events.append("cancelled")

    dialog = PasswordChangeDialog(
        _password_dialog_owner(root), Controller(),
        current_password="temporary-password",
        on_complete=lambda: events.append("opened"),
        on_cancel=lambda: events.append("login-reset"),
    )
    dialog.new_password.insert(0, "new-secure-password")
    dialog.confirm_password.insert(0, "new-secure-password")
    dialog._save()
    dialog._save()
    pump(root, lambda: "opened" in events)
    assert events == [("temporary-password", "new-secure-password"), "opened"]


def test_password_change_failure_restores_dialog(root):
    from app.views.login_view import PasswordChangeDialog

    class Controller:
        def change_password(self, current_password, new_password):
            return False, "Password service unavailable."

        def cancel_pending_login(self):
            return None

    dialog = PasswordChangeDialog(
        _password_dialog_owner(root), Controller(),
        current_password="temporary-password",
        on_complete=lambda: pytest.fail("Login must remain blocked"),
        on_cancel=lambda: None,
    )
    dialog.new_password.insert(0, "new-secure-password")
    dialog.confirm_password.insert(0, "new-secure-password")
    dialog._save()
    pump(root, lambda: not dialog.__dict__.get("_nexus_ui_task"))
    assert dialog.winfo_exists()
    assert dialog.save_button.cget("state") == "normal"
    assert "unavailable" in dialog.message.cget("text").lower()
    dialog._closed = True
    dialog.destroy()


def test_three_second_failed_login_keeps_ui_responsive_and_restores_controls(root):
    from app.views.login_view import LoginView
    main = threading.get_ident()
    ticks = []

    class Controller:
        requires_password_change = False

        def login(self, username, password, **kwargs):
            assert threading.get_ident() != main
            time.sleep(3)
            return False, "Cannot connect to the server."

    class Harness(ctk.CTkFrame):
        _submit = LoginView._submit
        _finish_login = LoginView._finish_login
        PRIMARY = PRIMARY_HOVER = "#60920d"
        DISABLED = "#888888"

        def _reset_login_button(self):
            self.login_button.configure(state="normal", text="Sign in")

    view = Harness(root)
    view._controller = Controller()
    view._is_destroyed = False
    view._login_success = False
    view.username_entry = ctk.CTkEntry(view)
    view.username_entry.insert(0, "person@example.test")
    view.password_entry = ctk.CTkEntry(view)
    view.password_entry.insert(0, "test-password")
    view.login_button = ctk.CTkButton(view)
    view._loading_label = ctk.CTkLabel(view)
    view.error_label = ctk.CTkLabel(view)

    def heartbeat():
        ticks.append(time.monotonic())
        if view.winfo_exists():
            root.after(25, heartbeat)

    heartbeat()
    started = time.monotonic()
    view._submit()
    assert time.monotonic() - started < .5
    assert view.login_button.cget("state") == "disabled"
    pump(root, lambda: not view.__dict__.get("_nexus_ui_task"))
    assert view.login_button.cget("state") == "normal"
    assert "cannot connect" in view.error_label.cget("text").lower()
    assert len(ticks) > 60
    view.destroy()
