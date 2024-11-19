from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urlparse
import re
from PIL import Image
import io

class WebsiteScraper:
    def __init__(self, output_directory="output", viewport_height=1080):
        """Initialize the scraper with Chrome options and output directory."""
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--start-maximized')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-animations')
        self.chrome_options.add_argument('--blink-settings=imagesEnabled=true')
        self.chrome_options.add_argument('--disable-javascript')
        
        self.viewport_height = viewport_height
        self.output_dir = output_directory
        os.makedirs(self.output_dir, exist_ok=True)
    
    def get_safe_filename(self, url):
        """Generate a safe filename from URL."""
        domain = urlparse(url).netloc
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"{re.sub(r'[^a-zA-Z0-9]', '_', domain)}_{timestamp}"
    
    def scroll_page(self, driver):
        """Scroll through the page to trigger lazy loading."""
        # Get initial page height
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(2)
            
            # Calculate new scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            # Break the loop if no more new content
            if new_height == last_height:
                break
            last_height = new_height
            
        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    
    def wait_for_content(self, driver, timeout=10):
        """Optimized initial content wait"""
        try:
            # Wait for body only
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Quick readyState check
            WebDriverWait(driver, 5).until(
                lambda x: x.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            print("Warning: Proceeding with partial load")
    
    def capture_full_page(self, driver, url):
        """Optimized version of capture_full_page"""
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_width = driver.execute_script("return document.documentElement.clientWidth")
        
        screenshots = []
        offset = 0
        
        # Increase scroll step size and reduce overlap
        scroll_step = int(self.viewport_height * 0.95)  # 5% overlap instead of 10%
        
        while offset < total_height:
            driver.execute_script(f"window.scrollTo(0, {offset});")
            
            # Reduced wait time
            time.sleep(0.5)  # Reduced from 1 second
            
            # Quick check for visible images
            self.quick_content_check(driver)
            
            screenshot = driver.get_screenshot_as_png()
            screenshots.append(Image.open(io.BytesIO(screenshot)))
            
            offset += scroll_step
            
            # Quick check for height changes
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height

        return self.stitch_screenshots(screenshots)

    def quick_content_check(self, driver, timeout=2):
        """Faster version of wait_for_lazy_content"""
        try:
            # Simplified image check
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("""
                    const images = document.getElementsByTagName('img');
                    for (let img of images) {
                        const rect = img.getBoundingClientRect();
                        if (rect.top >= 0 && 
                            rect.top <= window.innerHeight && 
                            !img.complete) {
                            return false;
                        }
                    }
                    return true;
                """)
            )
        except TimeoutException:
            pass  # Continue anyway to maintain speed

    def stitch_screenshots(self, screenshots):
        """Optimized stitching process"""
        if not screenshots:
            return None
            
        # Use list comprehension for faster dimension calculation
        heights = [img.height for img in screenshots]
        total_height = sum(heights)
        max_width = max(img.width for img in screenshots)
        
        # Create image with optimized mode
        stitched = Image.new('RGB', (max_width, total_height), 'white')
        
        # Faster pasting
        y_offset = 0
        for img in screenshots:
            stitched.paste(img, (0, y_offset))
            y_offset += img.height
            
        return stitched

    def extract_text(self, html_content):
        """Extract readable text content from HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'head', 'title', 'meta', '[document]']):
            element.decompose()
        
        # Get text content
        text = soup.get_text(separator='\n')
        
        # Clean up text
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = '\n\n'.join(lines)
        
        return clean_text
    
    async def get_text_only(self, url):
        """Process website to get only text content."""
        base_filename = self.get_safe_filename(url)
        text_path = os.path.join(self.output_dir, f"{base_filename}.txt")
        
        # Add these options specifically for text extraction
        text_options = Options()
        # Copy existing arguments one by one
        for argument in self.chrome_options.arguments:
            text_options.add_argument(argument)
        
        # Add additional arguments for text extraction
        text_options.add_argument('--block-images')  # Block image loading for faster text extraction
        text_options.add_argument('--disable-javascript')  # Ensure JS is disabled for text
        
        driver = webdriver.Chrome(options=text_options)
        
        try:
            # Set shorter page load timeout for text
            driver.set_page_load_timeout(10)
            driver.get(url)
            
            # Shorter wait time for text content
            self.wait_for_content(driver, timeout=5)
            
            # Get page source and extract text
            page_source = driver.page_source
            text_content = self.extract_text(page_source)
            
            # Save text content
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            return {
                'text_path': text_path,
                'text_content': text_content,
                'success': True
            }
            
        except Exception as e:
            print(f"Text extraction error: {str(e)}")
            return {
                'error': str(e),
                'success': False
            }
            
        finally:
            driver.quit()

    async def get_screenshot_only(self, url):
        """Process website to get only screenshot."""
        base_filename = self.get_safe_filename(url)
        screenshot_path = os.path.join(self.output_dir, f"{base_filename}.png")
        
        # Use regular chrome options with images enabled
        driver = webdriver.Chrome(options=self.chrome_options)
        
        try:
            # Longer timeout for screenshot as it needs images
            driver.set_page_load_timeout(30)
            driver.get(url)
            
            # Wait longer for images to load
            self.wait_for_content(driver, timeout=15)
            
            # Capture full page screenshot
            full_page_screenshot = self.capture_full_page(driver, url)
            if full_page_screenshot:
                full_page_screenshot.save(screenshot_path)
                
            return {
                'screenshot_path': screenshot_path,
                'success': True
            }
            
        except Exception as e:
            print(f"Screenshot error: {str(e)}")
            return {
                'error': str(e),
                'success': False
            }
            
        finally:
            driver.quit()

# Example usage
if __name__ == "__main__":
    url = "https://mercury.com"
    scraper = WebsiteScraper()
    result = scraper.process_website(url, wait_time=5)
    
    if result['success']:
        print("\nProcessing completed successfully!")
        print(f"Screenshot: {result['screenshot_path']}")
        print(f"Text content: {result['text_path']}")
    else:
        print(f"\nProcessing failed: {result.get('error', 'Unknown error')}")