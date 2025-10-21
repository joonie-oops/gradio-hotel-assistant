import os
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
import json
import sqlite3

# === Step 1: Load environment variables ===
load_dotenv(override=True)
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    raise ValueError("❌ OPENAI_API_KEY not found in .env file")

client = OpenAI(api_key=openai_api_key)

# === Step 2: Define system prompt ===
SYSTEM_PROMPT = (
    "You are a warm, professional hotel receptionist at Marina Vista Hotel, "
    "a luxury hotel located in Singapore's Marina Bay area. "
    "You greet guests politely, help with room reservations, local attractions, "
    "check-in/check-out information, and answer general questions about the hotel or Singapore. "
    "Keep your tone friendly, concise, and helpful, as if speaking to an international guest. "
    "Use a touch of hospitality language, but avoid being overly formal."
)

DB_PATH = "hotel.db"


def initialize_database(db_path=DB_PATH):
    """Create a SQLite database and seed it with room data (only if not exists)."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create table if not exists
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            price_per_night REAL,
            availability INTEGER
        )
    """
    )

    # Insert data only if table is empty
    c.execute("SELECT COUNT(*) FROM rooms")
    count = c.fetchone()[0]
    if count == 0:
        rooms = [
            (
                "Deluxe Suite",
                "Spacious suite with a king bed, private balcony, and panoramic bay view.",
                420,
                6,
            ),
            (
                "Ocean View Room",
                "Elegant room with ocean-facing windows and a queen bed.",
                320,
                4,
            ),
            (
                "Garden View Room",
                "Cozy room overlooking the hotel gardens, ideal for couples.",
                250,
                1,
            ),
            (
                "Standard Room",
                "Comfortable, affordable option with all essential amenities.",
                180,
                10,
            ),
        ]
        c.executemany(
            """
            INSERT INTO rooms (name, description, price_per_night, availability)
            VALUES (?, ?, ?, ?)
        """,
            rooms,
        )
        print("Database initialized with room data.")
    else:
        print("Database already initialized — skipping seeding.")

    conn.commit()
    conn.close()


# === Run this only once ===
if not os.path.exists(DB_PATH):
    initialize_database()
else:
    print("Database already exists — initialization skipped.")


# === MAIN FUNCTION ===
def get_room_details(room_type: str, db_path="hotel.db"):
    """
    Fetch room details from SQLite.
    If 'room_type' is 'all' or 'available', returns all or all available rooms.
    Otherwise, returns details for a specific room type.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    room_type = room_type.strip().lower()

    if room_type in ["all", "rooms"]:
        c.execute("SELECT name, description, price_per_night, availability FROM rooms")
    elif room_type == "available":
        c.execute(
            "SELECT name, description, price_per_night, availability FROM rooms WHERE availability > 0"
        )
    else:
        c.execute(
            "SELECT name, description, price_per_night, availability FROM rooms WHERE LOWER(name) = ?",
            (room_type,),
        )

    rows = c.fetchall()
    conn.close()

    if not rows:
        return {
            "error": f"Room type '{room_type}' not found. Try one of: Deluxe Suite, Ocean View Room, Garden View Room, Standard Room."
        }

    # Format result nicely as dict
    results = {
        name: {"description": desc, "price_per_night": price, "availability": avail}
        for name, desc, price, avail in rows
    }
    return results


def checkout_room(room_type: str, db_path="hotel.db"):
    """
    Reserve a room by name if available and return updated reservation details.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    normalized_room = room_type.strip().lower()
    c.execute(
        """
        SELECT id, name, description, price_per_night, availability
        FROM rooms
        WHERE LOWER(name) = ?
        """,
        (normalized_room,),
    )
    row = c.fetchone()

    if not row:
        conn.close()
        return {
            "error": f"Room type '{room_type}' not found. Try one of: Deluxe Suite, Ocean View Room, Garden View Room, Standard Room."
        }

    room_id, name, description, price_per_night, availability = row

    if availability <= 0:
        conn.close()
        return {
            "error": f"'{name}' is fully booked at the moment. Would you like to choose a different room type?"
        }

    new_availability = availability - 1
    c.execute(
        "UPDATE rooms SET availability = ? WHERE id = ?",
        (new_availability, room_id),
    )
    conn.commit()
    conn.close()

    return {
        "room": name,
        "description": description,
        "price_per_night": price_per_night,
        "remaining_availability": new_availability,
        "message": f"Reservation confirmed for {name}.",
    }


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_room_details",
            "description": (
                "Provide details about available rooms and their prices. "
                "If the guest wants information on all rooms, pass 'all' as the room_type."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "description": (
                            "Type of room the guest is interested in "
                            "(e.g. 'Deluxe Suite', 'Ocean View Room', or 'all' to list all)."
                        ),
                    },
                },
                "required": ["room_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "checkout_room",
            "description": (
                "Reserve a specific room if available and provide the booking details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "room_type": {
                        "type": "string",
                        "description": "Name of the room to reserve (e.g. 'Deluxe Suite').",
                    }
                },
                "required": ["room_type"],
            },
        },
    },
]


def respond(message, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for user, assistant in history:
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})

    messages.append({"role": "user", "content": message})

    while True:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        message_obj = response.choices[0].message
        messages.append(message_obj)

        # If LLM calls tools, handle them
        if message_obj.tool_calls:
            for tool_call in message_obj.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")

                if name == "get_room_details":
                    result = get_room_details(**args)
                elif name == "checkout_room":
                    result = checkout_room(**args)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                # Append tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            # Continue loop in case model chains multiple calls
            continue

        # If no tool calls, final message reached
        return message_obj.content


# === Step 4: Build Gradio Chat Interface ===
chat = gr.ChatInterface(
    fn=respond,
    title="🏨 Marina Vista Hotel Receptionist",
    description="Your friendly AI receptionist — here to help with bookings, amenities, and travel tips.",
)

# === Step 5: Launch ===
if __name__ == "__main__":
    chat.launch()
