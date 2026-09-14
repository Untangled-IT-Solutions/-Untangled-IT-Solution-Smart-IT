# CI Fix – Missing .env.example

## Problem
`tests/test_config.py::test_env_example_has_no_secrets` fails with:
FileNotFoundError: [Errno 2] No such file or directory: '.env.example'

Because the job runs with `working-directory: App`.

## You said
You are **not** using environment variables – the app makes HTTPS API calls instead.

## Recommended actions (pick one)

### 1. Cleanest – remove the obsolete test
Delete the entire `test_env_example_has_no_secrets` function from:
App/tests/test_config.py

### 2. Keep the test but make it skip when the file is absent
Replace the function with the content of `test_config_patch.py`.

### 3. Just make the current test pass
Copy `.env.example` into the `App/` folder (it contains only comments, zero secrets).

After applying any of the above, push and the CI job should go green again.
