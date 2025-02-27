import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Union
import logging

class ErrorPageService:
    def __init__(self, domain: Union[str, List[str]]):
        """
        Initialize the ErrorPageService with a domain or list of domains.
        
        Args:
            domain: The domain to check for error pages, or a list of URLs
        """
        if isinstance(domain, list):
            # If a list is provided, use it directly as the pages to check
            self.domain = None
            self.pages = domain
            self.base_url = None
        else:
            # If a single domain is provided, set it up for sitemap crawling
            self.domain = domain
            self.pages = []
            self.base_url = f"https://{domain}" if not domain.startswith(('http://', 'https://')) else domain

    async def get_all_pages_from_sitemap(self) -> List[str]:
        """
        Get all pages from the sitemap.xml of the domain.
        If sitemap.xml is not found, add the root URL.
        
        Returns:
            List of URLs to check
        """
        # If we already have pages from constructor, return them
        if self.pages and not self.domain:
            return self.pages
            
        # Otherwise fetch from sitemap
        sitemap_url = f"{self.base_url}/sitemap.xml"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=10) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), 'xml')
                        urls = soup.find_all('loc')
                        
                        if urls:
                            self.pages = [url.text for url in urls]
                        else:
                            # If sitemap doesn't contain URLs, add the root URL
                            self.pages = [self.base_url]
                    else:
                        # If sitemap doesn't exist, add the root URL
                        self.pages = [self.base_url]
        except Exception as e:
            logging.error(f"Error fetching sitemap for {self.domain}: {str(e)}")
            # Add the root URL as fallback
            self.pages = [self.base_url]
            
        return self.pages

    async def check_single_page(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        """
        Check a single page for errors.
        
        Args:
            session: The aiohttp session to use
            url: The URL to check
            
        Returns:
            Dictionary with error details if an error is found, None otherwise
        """
        try:
            async with session.get(url, timeout=10, allow_redirects=True) as response:
                status = response.status
                if status >= 400:  # Error status code
                    return {
                        "url": url,
                        "status_code": status,
                        "error_message": response.reason
                    }
                return None
        except Exception as e:
            return {
                "url": url,
                "status_code": 0,
                "error_message": str(e)
            }

    async def get_errors_async(self) -> List[Dict[str, Any]]:
        """
        Asynchronously check all pages for errors.
        
        Returns:
            List of dictionaries with error details
        """
        errors = []
        
        if not self.pages:
            await self.get_all_pages_from_sitemap()
            
        async with aiohttp.ClientSession() as session:
            tasks = [self.check_single_page(session, url) for url in self.pages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict):
                    errors.append(result)
                    
        return errors

    async def check_error_pages(self) -> List[Dict[str, Any]]:
        """
        Check all pages in the sitemap for errors.
        
        Returns:
            List of dictionaries with error details
        """
        # Simply await the async task instead of using run_until_complete()
        errors_result = await self.get_errors_async()
        
        return errors_result