from btx_omni.app import create_app


def test_create_app_configures_api_prefix() -> None:
    app = create_app()

    assert app.title == "BTX Omni Prospect"
    assert app.url_path_for("health") == "/api/health"
