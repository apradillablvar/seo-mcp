from seo_mcp.server import mcp

def main():
    """Entry point for the seo-mcp package"""
    mcp.run(transport="http", host="0.0.0.0")

if __name__ == "__main__":
    main()