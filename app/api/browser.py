"""
Headless Browser API — REST endpoints for Cipher's browsing capabilities.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.core.logging import logger

router = APIRouter(prefix="/api/v1/browser", tags=["browser"])


class VisitRequest(BaseModel):
    url: str = Field(..., description="URL to visit")
    extract_text: bool = Field(default=True)
    extract_links: bool = Field(default=True)
    screenshot: bool = Field(default=False)
    scroll: bool = Field(default=False)
    wait_selector: Optional[str] = Field(default=None)


class ScreenshotRequest(BaseModel):
    url: str = Field(..., description="URL to screenshot")
    full_page: bool = Field(default=False)
    viewport_width: int = Field(default=1280)
    viewport_height: int = Field(default=900)


class ExtractRequest(BaseModel):
    url: str = Field(..., description="URL to extract from")
    selectors: dict[str, str] = Field(..., description="Field name -> CSS selector mapping")


class ScrapeProductsRequest(BaseModel):
    url: str = Field(..., description="E-commerce URL to scrape")
    product_selector: str = Field(default=".product, .product-card, [data-product]")


@router.get("/status")
async def browser_status():
    """Get current browser status."""
    from app.services.headless_browser import get_status
    return get_status()


@router.post("/visit")
async def visit_page(req: VisitRequest):
    """Visit a URL with full browser rendering."""
    from app.services.headless_browser import visit_page as _visit

    result = await _visit(
        url=req.url,
        extract_text=req.extract_text,
        extract_links=req.extract_links,
        take_screenshot=req.screenshot,
        scroll_to_bottom=req.scroll,
        wait_selector=req.wait_selector,
    )

    output = result.to_dict()
    if result.text:
        output["text"] = result.text[:10000]
    if result.links:
        output["links"] = result.links[:50]
    if result.screenshot_b64:
        output["screenshot_b64"] = result.screenshot_b64

    return output


@router.post("/screenshot")
async def screenshot(req: ScreenshotRequest):
    """Take a screenshot of a URL."""
    from app.services.headless_browser import take_screenshot as _ss

    result = await _ss(
        url=req.url,
        full_page=req.full_page,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "url": result.url,
        "title": result.title,
        "screenshot_b64": result.screenshot_b64,
        "execution_time_ms": result.execution_time_ms,
    }


@router.post("/extract")
async def extract_data(req: ExtractRequest):
    """Extract structured data using CSS selectors."""
    from app.services.headless_browser import extract_structured_data

    result = await extract_structured_data(url=req.url, selectors=req.selectors)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return result.to_dict() | {"metadata": result.metadata}


@router.post("/scrape-products")
async def scrape_products(req: ScrapeProductsRequest):
    """Scrape product listings from an e-commerce page."""
    from app.services.headless_browser import scrape_product_pages

    result = await scrape_product_pages(url=req.url, product_selector=req.product_selector)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return result.to_dict() | {"products": result.metadata.get("products", []), "page_data": result.metadata.get("page_data", {})}


@router.post("/shutdown")
async def shutdown_browser():
    """Manually shut down the browser to free RAM."""
    from app.services.headless_browser import shutdown, is_running

    if not is_running():
        return {"status": "already_stopped"}

    await shutdown()
    return {"status": "stopped", "message": "Browser shut down — RAM freed"}
