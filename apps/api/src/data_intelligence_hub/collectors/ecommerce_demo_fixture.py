from __future__ import annotations

from urllib.parse import urlparse


def demo_ecommerce_html(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "shop.example":
        return None

    path = parsed.path.rstrip("/") or "/"
    if path == "/collections/summer-bags":
        return _summer_bags_collection_html()
    if path in {"/products/demo-bag", "/collections/summer-bags/products/demo-bag"}:
        return _demo_bag_product_html()
    if path == "/products/weekend-tote":
        return _weekend_tote_product_html()
    return None


def _summer_bags_collection_html() -> str:
    return """
    <html>
      <head>
        <title>Summer Bags</title>
        <link rel="canonical" href="/collections/summer-bags">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "item": {
                "@type": "Product",
                "name": "Demo Carry Bag",
                "url": "/products/demo-bag"
              }
            },
            {
              "@type": "ListItem",
              "item": {
                "@type": "Product",
                "name": "Weekend Tote",
                "url": "/products/weekend-tote"
              }
            }
          ]
        }
        </script>
        <script src="https://cdn.shopify.com/theme.js"></script>
      </head>
      <body>
        <h1>Summer Bags</h1>
        <p>Summer Bags Demo Carry Bag Weekend Tote</p>
        <a href="/products/demo-bag">Demo Carry Bag</a>
        <a href="/collections/summer-bags/products/demo-bag?variant=black">Demo Carry Bag Black</a>
        <a href="/products/weekend-tote">Weekend Tote</a>
        <a href="/collections/summer-bags?page=2" rel="next">Next</a>
        <a href="/pages/about">About</a>
      </body>
    </html>
    """


def _demo_bag_product_html() -> str:
    return """
    <html>
      <head>
        <title>Demo Shopify Product</title>
        <link rel="canonical" href="/products/demo-bag">
        <meta property="og:image" content="/cdn/demo.jpg">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Demo Carry Bag",
          "sku": "BAG-001",
          "brand": {"@type": "Brand", "name": "Demo Brand"},
          "category": ["Bags", "Summer"],
          "description": "A compact product fixture.",
          "image": ["/cdn/demo.jpg"],
          "hasVariant": [
            {"@type": "Product", "name": "Black", "sku": "BAG-001-BLK"},
            {"@type": "Product", "name": "Sand", "sku": "BAG-001-SAND"}
          ],
          "offers": [
            {
              "@type": "Offer",
              "name": "Black",
              "sku": "BAG-001-BLK",
              "price": "129.90",
              "priceCurrency": "USD",
              "availability": "https://schema.org/InStock"
            },
            {
              "@type": "Offer",
              "name": "Sand",
              "sku": "BAG-001-SAND",
              "price": "139.90",
              "priceCurrency": "USD",
              "availability": "https://schema.org/OutOfStock"
            }
          ]
        }
        </script>
        <script src="https://cdn.shopify.com/theme.js"></script>
      </head>
      <body>
        <h1>Demo Carry Bag</h1>
        <p>A compact product fixture for automation training.</p>
      </body>
    </html>
    """


def _weekend_tote_product_html() -> str:
    return """
    <html>
      <head>
        <title>Weekend Tote</title>
        <link rel="canonical" href="/products/weekend-tote">
        <meta property="og:image" content="/cdn/weekend-tote.jpg">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Weekend Tote",
          "brand": {"@type": "Brand", "name": "Demo Brand"},
          "category": "Bags",
          "description": "A tote fixture with intentionally incomplete commercial fields.",
          "image": ["/cdn/weekend-tote.jpg"],
          "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "availability": "https://schema.org/PreOrder"
          }
        }
        </script>
        <script src="https://cdn.shopify.com/theme.js"></script>
      </head>
      <body>
        <h1>Weekend Tote</h1>
        <p>Price and SKU are intentionally absent so dataset quality checks can surface gaps.</p>
      </body>
    </html>
    """
