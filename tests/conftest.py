import os

# Fix the global timezone in all tests to UTC.
os.environ["TZ"] = "UTC"
