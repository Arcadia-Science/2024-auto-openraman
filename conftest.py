def pytest_addoption(parser):
    parser.addoption(
        "--environment",
        action="store",
        default="testing",
        help='Environment to use for pytest. Default is "testing".',
    )
