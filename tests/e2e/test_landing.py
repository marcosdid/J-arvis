import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_landing_page_shows_title(page: Page, orchestrator_url: str) -> None:
    page.goto(orchestrator_url)
    expect(page).to_have_title("J-arvis")
    expect(page.locator("h1")).to_have_text("J-arvis")
