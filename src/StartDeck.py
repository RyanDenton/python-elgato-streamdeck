#!/usr/bin/env python3

#         Python Stream Deck Library
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

# Example script showing basic library usage - updating key images with new
# tiles generated at runtime, and responding to button state change events.

import os
import threading
import json
import sys
import subprocess

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

# Folder location of image assets used by this example.
ASSETS_PATH = os.path.join(os.path.dirname(__file__), "Assets")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
CURRENT_PAGE = 1

# Generates a custom tile with run-time generated text and custom image via the
# PIL module.
def render_key_image(deck, icon_filename, font_filename, label_text):
    # Resize the source image asset to best-fit the dimensions of a single key,
    # leaving a margin at the bottom so that we can draw the key title
    # afterwards.
    icon = Image.open(icon_filename)

    margin = 0

    if label_text:
        margin = 20

    image = PILHelper.create_scaled_image(deck, icon, margins=[0, 0, margin, 0])

    # Load a custom TrueType font and use it to overlay the key index, draw key
    # label onto the image a few pixels from the bottom of the key.
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_filename, 14)
    draw.text((image.width / 2, image.height - 5), text=label_text, font=font, anchor="ms", fill="white")

    return PILHelper.to_native_format(deck, image)

# Returns the current styling information for a key. Readonly.
def get_current_key_style(deck, page_number, key, state):

    key_config = get_key_config(deck, page_number, key)
    if not key_config:
        return {}

    return {
        "button": key_config["button"],
        "icon": key_config["active_icon"],
        "label": key_config["active_label"],
    }

# Returns styling information for a key based on its position and state.
def get_key_style(deck, page_number, key, state):
    # Last button in the example application is the exit button.
    exit_key_index = deck.key_count() - 1

    font = "Roboto-Regular.ttf"
    font_location = os.path.join(ASSETS_PATH, font)

    name = "Button" + str(key)

     # Get the config for the individual key
    key_config = get_key_config(deck, page_number, key)
    if not key_config:
        return {}

    icon_type = ''
    label_type = ''

    toggle_key = key_config.get('toggle', None)


    if toggle_key:
        icon_type = "active_icon"
        label_type = "active_label"
        
        # When a button is pressed, invert the icon.
        if state == True:
            # Collect current values
            primary_icon = key_config["primary_icon"]
            primary_label = key_config.get("primary_label", '')
            secondary_icon = key_config["secondary_icon"]
            secondary_label = key_config.get("secondary_label", '')
            active_icon = key_config["active_icon"]
            active_label = key_config["active_label"]

            # Calculate the new state of the icon based on the active icon. Handles both FQDN and plain filenames.
            if active_icon == primary_icon or active_icon == os.path.join(ASSETS_PATH, primary_icon):
                icon_type = 'secondary_icon'
                label_type = 'secondary_label'
            else:
                icon_type = 'primary_icon'
                label_type = 'primary_label'
    else:
        if state == True:
            icon_type = "active_icon"
            label_type = "active_label"
        else: 
            icon_type = "primary_icon"
            label_type = "primary_label"

    icon = ''
    label = ''

    if key_config:
        icon = key_config.get(icon_type, '') or key_config.get("primary_icon", '')
        label = key_config.get(label_type, '') or key_config.get("primary_label", '') # This line forces us to NEVER change the label if we don't specify one for the secondary state. Can we improve this?

    icon_location = ''
    if icon:
        icon_location = os.path.join(ASSETS_PATH, icon)


    return {
        "name": name,
        "icon": icon_location,
        "font": font_location,
        "label": label
    }

# returns the config value for an entry matching the specified key, from the config file.
def get_key_config(deck, page_number, key):
    
    page = [p for p in PAGES if p["page_number"] == page_number][0]

    # Filter the array of key configs to just the one we are interested in.
    matching_key_configs = [k for k in page["keys"] if k["button"] == key]

    if matching_key_configs:
       key_config = matching_key_configs[0]
       return key_config

# sets the config value for an entry matching the specified key/config value.
def set_key_config_value(deck, page_number, key, config_item, value):
    current_key_config = get_key_config(deck, page_number, key)

    if current_key_config:
        key_config = current_key_config
        key_config[config_item] = value
    

# Creates a new key image based on the key index, style and current key state
# and updates the image on the StreamDeck.
def update_key_image(deck, page_number, key, state):

    print("update_key_image | Updating: page", page_number, " key ", key)

    # Determine what icon and label to use on the generated key.
    key_style = get_key_style(deck, page_number, key, state)

    if key_style and key_style["icon"]:

        # Generate the custom key with the requested image and label.
        image = render_key_image(deck, key_style["icon"], key_style["font"], key_style["label"])

        # Use a scoped-with on the deck to ensure we're the only thread using it
        # right now.
        with deck:
            # Update requested key with the generated image.
            deck.set_key_image(key, image)

        # Update the active elements in the config to reflect the new state of the key.
        set_key_config_value(deck, page_number, key, "active_icon", key_style["icon"])
        set_key_config_value(deck, page_number, key, "active_label", key_style["label"])

# Performs any configured actions for a button when it has been pressed.
def perform_key_actions(deck, page_number, key, state):
    if state:
        # Get config for the individual key
        key_config = get_key_config(deck, page_number, key)

        if key_config:
            display_page = key_config.get("display_page", None)
            if display_page:
                print('Changing display to page: ', display_page)
                load_page(deck, display_page)
                
                global CURRENT_PAGE
                CURRENT_PAGE = display_page

            action = key_config.get("action", None)
            if action:
                print('Performing action on key: ', key)
                subprocess.run(action, shell=True)

# Loads the keys for a specified page onto the Streamdeck.
def load_page(deck, page_number):
    page_layout = [p for p in PAGES if p["page_number"] == page_number][0] # Get the config for all the buttons on the specified page.

    # Update key images.
    if page_layout:
        deck.reset() # Reset the deck, clearing all current images.

        for key in page_layout["keys"]:
            update_key_image(deck, page_layout["page_number"], key["button"], False) # Update images to display the new page.
        
        global CURRENT_PAGE
        CURRENT_PAGE = page_layout.get("page_number", 'N/A')


# Prints key state change information, updates the key image and performs any
# associated actions when a key is pressed.
def key_change_callback(deck, key, state):
    # Print new key state
    print("BUTTON STATE CHANGE DETECTED: Deck {} Key {} = {}".format(deck.id(), key, state), flush=True)

    # Check if the key is changing to the pressed state.
    if state:

        # Update the key image based on the new key state.
        update_key_image(deck, CURRENT_PAGE, key, state)

        # Perform any actions assigned to the key currently only supports 
        # actions on button press, and not when a button released.
        perform_key_actions(deck, CURRENT_PAGE, key, state)

        key_style = get_current_key_style(deck, CURRENT_PAGE, key, state)

        # When an exit button is pressed, close the application.
        if key_style.get("button") == 14:
            # Use a scoped-with on the deck to ensure we're the only thread
            # using it right now.
            with deck:
                # Reset deck, clearing all button images.
                deck.reset()

                # Close deck handle, terminating internal worker threads.
                deck.close()


if __name__ == "__main__":
    streamdecks = DeviceManager().enumerate()

    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    for index, deck in enumerate(streamdecks):
        # This example only works with devices that have screens.
        if not deck.is_visual():
            continue

        deck.open()
        deck.reset()

        print("Opened '{}' device (serial number: '{}', fw: '{}')".format(
            deck.deck_type(), deck.get_serial_number(), deck.get_firmware_version()
        ))

        # Set initial screen brightness to 30%.
        deck.set_brightness(30)

        # Check for a user specified config file.
        if len(sys.argv) > 1:
            if sys.argv[1] == "-c" or sys.argv[1] == "--config":
                CONFIG_PATH = sys.argv[2]
        
        DECK_CONFIG = json.load(open(CONFIG_PATH, 'r'))
        PAGES = DECK_CONFIG["pages"]
        HOME_PAGE = [p for p in PAGES if p["home_page"] == True][0] # Get the layout of the intial home screen.

        load_page(deck, HOME_PAGE["page_number"])

        # Register callback function for when a key state changes.
        deck.set_key_callback(key_change_callback)

        # Wait until all application threads have terminated (for this example,
        # this is when all deck handles are closed).
        for t in threading.enumerate():
            try:
                t.join()
            except RuntimeError:
                pass
