"""
SEO MCP Server: A free SEO tool MCP (Model Control Protocol) service based on Ahrefs data.
"""
import requests
import time
import os
import urllib.parse
from typing import Dict, List, Optional, Any, Literal

# Import FastAPI to create the main application
from fastapi import FastAPI
from fastmcp import FastMCP

from seo_mcp.backlinks import get_backlinks, load_signature_from_cache, get_signature_and_overview
from seo_mcp.keywords import get_keyword_ideas, get_keyword_difficulty
from seo_mcp.traffic import check_traffic

# 1. Create the main FastAPI application. This is our new "wrapper" app.
app = FastAPI(title="SEO MCP Wrapper")

# 2. Add a health check endpoint to the root path ('/').
# This will respond to Railway's health checks with a 200 OK status.
@app.get("/")
def health_check():
    print("--- HEALTH CHECK ENDPOINT WAS HIT ---")
    return {"status": "ok", "message": "SEO MCP is healthy"}

# 3. Create your MCP instance as you did before.
mcp = FastMCP("SEO MCP")

# --- All of your existing MCP tools are defined below ---
@mcp.tool()
def get_backlinks_list(domain: str) -> Optional[Dict[str, Any]]:
    """
    Get backlinks list for the specified domain
    Args:
        domain (str): The domain to query
    Returns:
        List of backlinks for the domain, containing title, URL, domain rating, etc.
    """
    # Using a helper function to consolidate token logic from your original file
    token = get_token_for_url(f"https://ahrefs.com/backlink-checker/?input={domain}&mode=subdomains")
    signature, valid_until, overview_data = get_signature_and_overview(token, domain)
    if not signature or not valid_until:
        raise Exception(f"Failed to get signature for domain: {domain}")

    backlinks = get_backlinks(signature, valid_until, domain)
    return {"overview": overview_data, "backlinks": backlinks}

@mcp.tool()
def keyword_generator(keyword: str, country: str = "us", search_engine: str = "Google") -> Optional[List[str]]:
    """Get keyword ideas for the specified keyword"""
    token = get_token_for_url(f"https://ahrefs.com/keyword-generator/?country={country}&input={urllib.parse.quote(keyword)}")
    return get_keyword_ideas(token, keyword, country, search_engine)

@mcp.tool()
def get_traffic(domain_or_url: str, country: str = "None", mode: Literal["subdomains", "exact"] = "subdomains") -> Optional[Dict[str, Any]]:
    """Check the estimated search traffic for any website."""
    token = get_token_for_url(f"https://ahrefs.com/traffic-checker/?input={domain_or_url}&mode={mode}")
    return check_traffic(token, domain_or_url, mode, country)

@mcp.tool()
def keyword_difficulty(keyword: str, country: str = "us") -> Optional[Dict[str, Any]]:
    """Get keyword difficulty for the specified keyword"""
    token = get_token_for_url(f"https://ahrefs.com/keyword-difficulty/?country={country}&input={urllib.parse.quote(keyword)}")
    return get_keyword_difficulty(token, keyword, country)

# --- Helper function to simplify getting the CapSolver token ---
def get_token_for_url(site_url: str) -> str:
    """Gets a captcha token for a given URL."""
    token = get_capsolver_token(site_url)
    if not token:
        raise Exception(f"Failed to get verification token for URL: {site_url}")
    return token

def get_capsolver_token(site_url: str) -> Optional[str]:
    """Uses CapSolver to solve the captcha and get a token."""
    api_key = os.environ.get("CAPSOLVER_API_KEY")
    if not api_key:
        print("Error: CAPSOLVER_API_KEY environment variable not set.")
        return None
    payload = {"clientKey": api_key, "task": {"type": 'AntiTurnstileTaskProxyLess', "websiteKey": "0x4AAAAAAAAzi9ITzSN9xKMi", "websiteURL": site_url}}
    try:
        res = requests.post("https://api.capsolver.com/createTask", json=payload, timeout=20)
        res.raise_for_status()
        resp = res.json()
        task_id = resp.get("taskId")
        if not task_id:
            return None
        while True:
            time.sleep(2)
            payload = {"clientKey": api_key, "taskId": task_id}
            res = requests.post("https://api.capsolver.com/getTaskResult", json=payload, timeout=20)
            res.raise_for_status()
            resp = res.json()
            if resp.get("status") == "ready":
                return resp.get("solution", {}).get('token')
            if resp.get("status") == "failed" or resp.get("errorId"):
                return None
    except requests.RequestException as e:
        print(f"Error communicating with CapSolver: {e}")
        return None

# 4. Mount the MCP's internal server onto our main app at the /mcp path.
# We use the internal _mcp_server attribute we discovered in previous debugging.
app.mount("/mcp", mcp._mcp_server)