# Gradio Hotel Assistant

A small Gradio chatbot that plays the role of the Marina Vista Hotel receptionist. It can answer questions about rooms and amenities by querying a local SQLite database and supports booking a room via the `checkout_room` tool.

## Requirements

- Python 3.11+
- An OpenAI API key with access to `gpt-4.1-mini` (or update the model name in the script)

## Setup

1. **Clone the repo & enter the folder**
   ```bash
   git clone git@github.com:joonie-oops/gradio-hotel-assistant.git
   cd gradio-hotel-assistant
   ```
2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Set your OpenAI credentials**  
   Create a `.env` file alongside the script:
   ```env
   OPENAI_API_KEY=sk-your-key
   ```
5. **Run the app**
   ```bash
   python gradio_hotel_receptionist_2.py
   ```

The app will create and seed `hotel.db` automatically the first time it runs. Gradio launches a local web UI where you can chat with the receptionist, get room details, and reserve rooms.
