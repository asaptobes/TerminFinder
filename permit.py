import asyncio
import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
YOUR_CHAT_ID = "YOUR_CHAT_ID_HERE" 
STUTTGART_PORTAL_URL = "https://stuttgart.konsentas.de/form/7/?signup_new=1"

# --- YOUR PERSONAL DETAILS (Ausländerbehörde Edition) ---
MY_DETAILS = {
    "vorname": "JOHN",            
    "nachname": "DOE",              
    "email": "JOHN@DOE.COM",
    "telefon": "+49 NUMBER HERE",
    "strasse": "A STREET",      
    "nummer": "100",                 
    "plz": "70173",                 
    "ort": "Stuttgart",             
    "geburtsdatum": "XX.XX.XXXX",
    "staatsangehoerigkeit": "ANYWHERE", 
    "passnummer": "123456789"                 
}

# --- STATE VARIABLES ---
appointment_found = False
booking_in_progress = False
browser_page = None
available_times = [] 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Stuttgart Ausländerbehörde Bot started! Hunting for your residence permit appointment...")

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global appointment_found, booking_in_progress, browser_page, available_times
    
    user_reply = update.message.text.strip().lower() 
    
    if user_reply == "resume":
        appointment_found = False
        booking_in_progress = False
        available_times = []
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Wiping session and resuming the search for appointments...")
        if browser_page:
            await browser_page.context.clear_cookies()
            await browser_page.goto(STUTTGART_PORTAL_URL)
        return

    exact_time = update.message.text.strip()
    if exact_time in available_times and appointment_found and not booking_in_progress:
        booking_in_progress = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Attempting to select {exact_time} and proceed...")
        
        try:
            time_button = browser_page.locator(f"button:has-text('{exact_time}'), a:has-text('{exact_time}'), div.time-slot:has-text('{exact_time}')").first
            await time_button.click(timeout=3000)
            
            await browser_page.wait_for_timeout(500) 
            
            weiter_button = browser_page.locator('button:has-text("Weiter"), input[value="Weiter"]')
            await weiter_button.first.click(timeout=3000)
            
            await browser_page.wait_for_load_state("networkidle")
            
            no_appointments_text = browser_page.locator("text=Keine verfügbaren Termine").first
            
            if await no_appointments_text.is_visible():
                logging.info("Appointment lost during booking. Restarting search...")
                appointment_found = False
                booking_in_progress = False
                available_times = []
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text="❌ Ah, bad news! Someone else grabbed that exact slot while we were clicking. Automatically resuming the search right now!"
                )
                if browser_page:
                    await browser_page.context.clear_cookies()
                    await browser_page.goto(STUTTGART_PORTAL_URL)
                
            else:
                available_times = []
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text="✅ Time secured! Automatically filling out your details now..."
                )
                
                # --- AUTO-FILL FORM LOGIC ---
                try:
                    await browser_page.fill('#vorname_input_id', MY_DETAILS["vorname"])
                    await browser_page.fill('#nachname_input_id', MY_DETAILS["nachname"])
                    await browser_page.fill('#email_input_id', MY_DETAILS["email"])
                    await browser_page.fill('#telefon_input_id', MY_DETAILS["telefon"])
                    await browser_page.fill('#strasse_input_id', MY_DETAILS["strasse"])
                    await browser_page.fill('#nummer_input_id', MY_DETAILS["nummer"]) 
                    await browser_page.fill('#plz_input_id', MY_DETAILS["plz"])
                    await browser_page.fill('#ort_input_id', MY_DETAILS["ort"])
                    await browser_page.fill('#geburtsdatum_input_id', MY_DETAILS["geburtsdatum"])

                    await context.bot.send_message(
                        chat_id=update.effective_chat.id, 
                        text="🎉 FORM FILLED! Check the browser window NOW to confirm everything is correct and click Submit!\n\nReply 'resume' to start searching again later."
                    )
                
                except Exception as form_error:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id, 
                        text=f"⚠️ Made it to the form, but couldn't auto-fill some details. Please complete it manually in the browser! Error: {form_error}"
                    )
            
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error selecting time: {e}. Resuming search...")
            appointment_found = False
            booking_in_progress = False
            available_times = []
            if browser_page:
                await browser_page.context.clear_cookies()
                await browser_page.goto(STUTTGART_PORTAL_URL)
            
    elif user_reply == "no" and appointment_found:
        appointment_found = False
        available_times = []
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Skipped. I'll resume searching.")
        if browser_page:
            await browser_page.context.clear_cookies()
            await browser_page.goto(STUTTGART_PORTAL_URL)
            
    elif appointment_found:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"Please reply with an exact time from the list ({', '.join(available_times)}) or 'no'."
        )

async def check_appointments(bot_app):
    global appointment_found, browser_page, available_times
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context()
        browser_page = await context.new_page()
        
        while True:
            if not appointment_found and not booking_in_progress:
                try:
                    logging.info("Checking for new appointments...")
                    
                    await context.clear_cookies()
                    
                    # Added wait_until to ensure the page is actually ready before we start clicking
                    await browser_page.goto(STUTTGART_PORTAL_URL, wait_until="domcontentloaded")
                    
                    # 1. Click "Ausländerbehörde - Servicepoint"
                    try:
                        category_btn = browser_page.locator('text="Ausländerbehörde - Servicepoint"').first
                        await category_btn.click(timeout=3000)
                        await browser_page.wait_for_timeout(1000) 
                        logging.info("Expanded the Servicepoint menu.")
                    except Exception as e:
                        logging.warning(f"Could not click category menu: {e}")

                    # 2. Open the custom dropdown menu
                    try:
                        service_container = browser_page.locator('div[data-process-name="Übertragung bestehender Aufenthaltstitel auf neuen Nationalpass (sog. Übertrag)"]')
                        
                        dropdown_btn = service_container.locator('button.dropdown-toggle')
                        await dropdown_btn.click(timeout=3000)
                        await browser_page.wait_for_timeout(500) 
                        
                        option_1_person = service_container.locator('a[data-option-name="1 Person"]')
                        await option_1_person.click(timeout=3000)
                        logging.info("Selected '1 Person' from the custom dropdown.")
                    except Exception as e:
                        logging.warning(f"Could not select 1 Person from custom dropdown: {e}")

                    # 3. Click the custom label to activate the green checkmark
                    try:
                        service_label = browser_page.locator('label[data-process-name="Übertragung bestehender Aufenthaltstitel auf neuen Nationalpass (sog. Übertrag)"]')
                        await service_label.click(timeout=3000)
                        logging.info("Activated the service radio button!")
                    except Exception as e:
                        logging.warning(f"Could not click the service radio button: {e}")

                    # 4. Click the FIRST "Weiter" (Next) button
                    # --- THE FIX: SAFETY ABORT ---
                    try:
                        weiter_button = browser_page.locator('button:has-text("Weiter"), input[value="Weiter"]')
                        await weiter_button.first.click(timeout=3000)
                        logging.info("Successfully clicked the FIRST Weiter button!")
                    except Exception as e:
                        # If we can't click Weiter, the form is broken. Raise an exception to restart the 60-sec loop instantly!
                        raise Exception(f"CRITICAL: Failed to click FIRST Weiter button. Aborting this attempt. Details: {e}")
                    
                    await browser_page.wait_for_load_state("networkidle")
                    
                    # 5. Click the SECOND "Weiter" button
                    try:
                        await browser_page.wait_for_timeout(1000)
                        weiter_button_2 = browser_page.locator('button:has-text("Weiter"), input[value="Weiter"]')
                        await weiter_button_2.first.click(timeout=3000)
                        logging.info("Successfully clicked the SECOND Weiter button!")
                    except Exception as e:
                        # Safety Abort here too!
                        raise Exception(f"CRITICAL: Failed to click SECOND Weiter button. Aborting. Details: {e}")

                    await browser_page.wait_for_load_state("networkidle")
                    await browser_page.wait_for_timeout(2000) 
                    
                    no_appointments_text = browser_page.locator("text=Keine verfügbaren Termine").first
                    
                    if await no_appointments_text.is_visible():
                        logging.info("No appointment found - trying again in 60 seconds")
                    else:
                        appointment_found = True
                        logging.info("Appointment page reached! Trying to click a date...")
                        
                        await browser_page.wait_for_timeout(2000)
                        
                        try:
                            available_day = browser_page.locator('.available, .free, td a, .ui-state-default:not(.ui-state-disabled)').first
                            await available_day.click(timeout=3000)
                            logging.info("Clicked an available calendar day!")
                            
                            await browser_page.wait_for_timeout(1500)
                        except Exception as e:
                            logging.warning(f"Could not automatically click the calendar day: {e}")
                            
                        logging.info("Scraping times...")
                        
                        all_text_elements = await browser_page.locator("body").inner_text()
                        
                        scraped_times = re.findall(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b', all_text_elements)
                        
                        available_times = sorted(list(set(scraped_times)))
                        
                        if available_times:
                            times_str = ", ".join(available_times)
                            msg = f"🚨 APPOINTMENT(S) FOUND! 🚨\n\nAvailable times:\n{times_str}\n\nReply with the EXACT time you want (e.g., '{available_times[0]}'), or 'no' to skip."
                        else:
                            msg = "🚨 APPOINTMENT FOUND! 🚨\n\n(I couldn't read the times automatically. Please check the visible browser window immediately!)"
                            available_times = ['yes'] 
                        
                        await bot_app.bot.send_message(chat_id=YOUR_CHAT_ID, text=msg)
                
                except Exception as e:
                    # If the safety abort triggers, it lands here and safely prepares to restart.
                    logging.error(f"Error checking page: {e}")
            
            await asyncio.sleep(60)

async def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_response))
    
    asyncio.create_task(check_appointments(application))
    
    await application.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    
    asyncio.run(main())