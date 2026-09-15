"""Sequential UI workflows with explicit worker boundaries.

@ui_task methods are generators. `yield RemoteCall(service.method, *values)`
evaluates widget-derived arguments on Tk, runs only the service method in a
worker, then resumes the generator (including try/except/finally) on Tk.
Use `yield from ui_steps(self.helper, ...)` for dependent UI helpers.
"""
from functools import wraps
import inspect
import tkinter as tk
from app.utils.async_tasks import run_in_background

class RemoteCall:
    def __init__(self, function, *args, **kwargs):
        self.function, self.args, self.kwargs = function, args, kwargs
    def __call__(self):
        return self.function(*self.args, **self.kwargs)


def ui_steps(method, *args, **kwargs):
    original = getattr(method, '__wrapped__', None)
    result = original(method.__self__, *args, **kwargs) if original else method(*args, **kwargs)
    if inspect.isgenerator(result):
        return (yield from result)
    return result


def action_steps(action):
    # Widget reads in action lambdas run on Tk before yielding a RemoteCall.
    result = action()
    if inspect.isgenerator(result):
        return (yield from result)
    return result


def ui_task(function):
    @wraps(function)
    def start(owner, *args, **kwargs):
        if owner.__dict__.get('_nexus_ui_task'):
            if function.__name__ in {'refresh', '_refresh_all', '_show_profile', '_change_month', '_apply_filters', '_go_today', '_select_day', '_clear_filters', '_show_all'}:
                owner._nexus_pending_refresh = lambda: start(owner, *args, **kwargs)
            return None
        workflow = function(owner, *args, **kwargs)
        if not inspect.isgenerator(workflow):
            return workflow
        token = object()
        owner._nexus_ui_task = token
        overlay = None
        completed = False
        def alive():
            try:
                return owner.winfo_exists() and not getattr(owner, '_is_destroyed', False)
            except Exception:
                return False
        def finish():
            nonlocal completed
            completed = True
            if owner.__dict__.get('_nexus_ui_task') is token:
                owner._nexus_ui_task = None
            if overlay is not None:
                try:
                    overlay.destroy()
                except tk.TclError:
                    pass
            pending = getattr(owner, '_nexus_pending_refresh', None)
            owner._nexus_pending_refresh = None
            if pending and alive():
                owner.after_idle(pending)
        def resume(value=None, error=None):
            nonlocal overlay
            if completed:
                return
            if overlay is not None and not alive():
                finish()
                return
            try:
                request = workflow.throw(error) if error else workflow.send(value)
                if not isinstance(request, RemoteCall):
                    raise TypeError('UI workflows must yield RemoteCall objects.')
                if overlay is None:
                    overlay = tk.Frame(owner, bg='#f3f6f0', borderwidth=1, relief='solid')
                    text = 'Signing in...' if owner.__class__.__name__ == 'LoginView' else 'Loading... Please wait.'
                    tk.Label(overlay, text=text, bg='#f3f6f0', padx=18, pady=12).pack(expand=True)
                    overlay.place(x=0, y=0, relwidth=1, relheight=1)
                    overlay.lift()
                run_in_background(owner, request, lambda result: resume(result), lambda exc: resume(error=exc), name='nexus-' + function.__name__)
            except StopIteration:
                finish()
            except Exception as exc:
                finish()
                if alive():
                    from tkinter import messagebox
                    messagebox.showerror('Nexus', str(exc) or 'The request failed. Please try again.', parent=owner)
        resume()
        return None
    return start


def ui_callback(owner):
    """Adapt a nested UI callback that closes over its owning view."""
    def decorate(function):
        @ui_task
        def workflow(_owner, *args, **kwargs):
            return (yield from function(*args, **kwargs))
        @wraps(function)
        def callback(*args, **kwargs):
            return workflow(owner, *args, **kwargs)
        return callback
    return decorate
