import gradio as gr
from script import WebsiteScraper
import asyncio
import google.generativeai as genai
import os

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'AIzaSyA6iJsqMP8qZlVItyAuTxN0lbqW0Bgkzzo'))

# Create the model with configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

async def process_compliance_check(website_url, compliance_url, compliance_text):
    """
    Process websites and check compliance using Gemini API with progressive updates
    """
    scraper = WebsiteScraper()
    
    progress = gr.Progress()
    progress(0, desc="Getting website text...")
    # Get main website text first
    main_text_result = await scraper.get_text_only(website_url)
    if not main_text_result['success']:
        yield None, "Error processing main website text", None, "Failed to process website"
        return  # Early return without value
    
    # Yield the first update with website text
    yield None, main_text_result['text_content'], None, "Processing..."
    
    progress(0.25, desc="Getting compliance text...")
    # Get compliance text
    compliance_result = await scraper.get_text_only(compliance_url)
    if not compliance_result['success']:
        yield None, main_text_result['text_content'], "Error processing compliance website", "Failed to process compliance website"
        return  # Early return without value
    
    # Yield update with compliance text
    yield None, main_text_result['text_content'], compliance_result['text_content'], "Processing..."
    
    progress(0.5, desc="Capturing screenshot...")
    # Get screenshot (takes longer)
    main_screenshot_result = await scraper.get_screenshot_only(website_url)
    if not main_screenshot_result['success']:
        yield None, main_text_result['text_content'], compliance_result['text_content'], "Error processing screenshot"
        return  # Early return without value
    
    # Yield update with screenshot
    yield main_screenshot_result['screenshot_path'], main_text_result['text_content'], compliance_result['text_content'], "Analyzing..."

    try:
        progress(0.75, desc="Analyzing compliance...")
        # Prepare compliance text
        final_compliance_text = compliance_text
        if compliance_result['text_content']:
            final_compliance_text = f"{compliance_result['text_content']}\n\nExtra Compliance Requirements: {compliance_text}"

        # Upload screenshot and process with Gemini
        screenshot_file = genai.upload_file(main_screenshot_result['screenshot_path'], mime_type="image/png")
        chat = model.start_chat(history=[])
        
        prompt = f"""
        Given the following \"Website Image\", and \"Website Text\" as provided in the input...
        # ... rest of your prompt ...
        """
        
        response = chat.send_message([screenshot_file, prompt])
        
        # Final yield with complete results
        yield (
            main_screenshot_result['screenshot_path'],
            main_text_result['text_content'],
            compliance_result['text_content'],
            response.text
        )
        
    except Exception as e:
        yield (
            main_screenshot_result['screenshot_path'],
            main_text_result['text_content'],
            compliance_result['text_content'],
            f"Error in Gemini API processing: {str(e)}"
        )

# Create Gradio Interface
with gr.Blocks(title="Website Compliance Checker") as demo:
    gr.Markdown("# Website Compliance Checker")
    
    with gr.Row():
        with gr.Column():
            # Inputs
            website_url = gr.Textbox(
                label="Website to check Compliance for",
                placeholder="Enter website URL (e.g., https://example.com)"
            )
            gr.Markdown("Compliance Information")
            compliance_url = gr.Textbox(
                label="Compliance Documentation Website",
                placeholder="Enter compliance documentation URL"
            )
            compliance_text = gr.Textbox(
                label="Compliance Text",
                placeholder="Enter compliance requirements",
                lines=3
            )
            submit_btn = gr.Button("Check Compliance", variant="primary")
            gr.Markdown("Result - Might take upto 2 mins to process")
            compliance_result = gr.Markdown(
                label="Compliance Check Result"
            )
            
        
        with gr.Column():
            # Outputs
            website_image = gr.Image(
                label="Website Screenshot",
                type="filepath"
            )
            website_text = gr.Textbox(
                label="Website Content",
                lines=10,
                max_lines=15
            )
            compliance_doc = gr.Textbox(
                label="Compliance Documentation",
                lines=10,
                max_lines=15
            )
    
    # Handle submission
    submit_btn.click(
        fn=process_compliance_check,
        inputs=[website_url, compliance_url, compliance_text],
        outputs=[website_image, website_text, compliance_doc, compliance_result],
        show_progress=True
    )

if __name__ == "__main__":
    port = int(os.getenv('PORT', 7860))
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port
    )