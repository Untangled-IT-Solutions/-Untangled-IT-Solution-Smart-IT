from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
nav_path = ROOT / 'app/controllers/navigation_controller.py'
app_path = ROOT / 'app/controllers/app_controller.py'
main_path = ROOT / 'app/views/main_window.py'
nav_src = nav_path.read_text(encoding='utf-8')
app_src = app_path.read_text(encoding='utf-8')
main_src = main_path.read_text(encoding='utf-8')

expected = ['Dashboard','People','Attendance','Calendar','Approvals','Office Requests','Notifications','Projects','Tasks','Reports','Quote Management','Order Management','Quote Sync','User Management','Settings']
ast.parse(nav_src); ast.parse(app_src); ast.parse(main_src)
for destination in expected:
    assert destination in nav_src, f'Missing navigation item: {destination}'
    assert destination in app_src, f'Missing view route reference: {destination}'
assert '_navigation_items_cache' in nav_src
assert '_navigation_busy' in nav_src
assert 'get_navigation_items(refresh=False)' in nav_src
assert 'Navigation click:' in main_src
assert 'self._navigation_controller = None' in main_src
print(f'NAVIGATION_ROUTE_TEST_OK: {len(expected)} destinations verified')
