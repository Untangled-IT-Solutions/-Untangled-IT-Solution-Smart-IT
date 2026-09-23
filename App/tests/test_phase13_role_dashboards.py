from types import SimpleNamespace

from app.controllers.dashboard_controller import DashboardController
from app.controllers.navigation_controller import NavigationController


class DashboardStub:
    def __init__(self):
        self.called = []

    def _call(self, name):
        self.called.append(name)
        return {"dashboard_type": name}

    def get_summary(self): return self._call("summary")
    def get_director_dashboard(self): return self._call("director")
    def get_business_lead_dashboard(self): return self._call("business_lead")
    def get_operations_dashboard(self): return self._call("operations")
    def get_personal_dashboard(self): return self._call("personal")


def test_controller_selects_role_specific_endpoint():
    for role, expected in (("Director", "director"), ("Business Lead", "business_lead"),
                           ("Operations Manager", "operations"), ("Staff", "personal"),
                           ("Intern", "personal")):
        service = DashboardStub()
        controller = DashboardController(service, lambda r=role: SimpleNamespace(role=r))
        assert controller.get_summary()["dashboard_type"] == expected
        assert service.called == [expected]


def test_staff_navigation_contains_only_personal_modules():
    account = SimpleNamespace(role="Staff", username="staff@test.invalid", full_name="Staff Person")
    nav = NavigationController(get_current_account=lambda: account)
    items = nav.get_navigation_items()
    assert {"Dashboard", "Tasks", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Settings"} == set(items)
    assert not ({"People", "Projects", "Reports", "Quote Management", "Order Management", "User Management"} & set(items))


def test_operations_navigation_exposes_command_modules():
    account = SimpleNamespace(role="Operations Manager", username="ops@test.invalid", full_name="Ops Person")
    nav = NavigationController(get_current_account=lambda: account)
    assert {"People", "Tasks", "Attendance", "Calendar", "Approvals", "Office Requests",
            "Notifications", "Projects", "Reports", "User Management"} <= set(nav.get_navigation_items())
