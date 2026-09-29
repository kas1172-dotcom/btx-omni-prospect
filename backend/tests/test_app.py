from btx_omni.app import create_app


def test_create_app_configures_api_prefix() -> None:
    app = create_app()

    # Project Beacon branding was adopted by the application before this test
    # was added; keep the assertion aligned with the intentional product name.
    assert app.title == "BTX Omni - Project Beacon"
    assert app.url_path_for("health") == "/api/health"
