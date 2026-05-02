from interface.runtime_checks import runtime_compatibility_errors


def test_runtime_check_rejects_django_42_on_python_314():
    errors = list(
        runtime_compatibility_errors(
            python_version=(3, 14),
            django_version=(4, 2),
        )
    )

    assert len(errors) == 1
    assert errors[0].id == "webhook.E001"
    assert "Django 4.2 supports Python 3.8 through 3.12." in errors[0].hint


def test_runtime_check_allows_django_42_on_python_312():
    errors = list(
        runtime_compatibility_errors(
            python_version=(3, 12),
            django_version=(4, 2),
        )
    )

    assert errors == []


def test_runtime_check_allows_newer_django_series_on_python_314():
    errors = list(
        runtime_compatibility_errors(
            python_version=(3, 14),
            django_version=(5, 2),
        )
    )

    assert errors == []
