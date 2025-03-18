# Yu-Gi-Oh! NFC Card Viewer

This is a PySide6-based graphical user interface (GUI) for viewing Yu-Gi-Oh! card details. It works in conjunction with the [Yu-Gi-Oh! Card NFC Server](https://github.com/your-repo-name/card-server) to display card information from NFC tags.

The application generates the card dynamically in the GUI by receiving JSON data from the card server and animating the card display with transitions.

## Requirements

- Python 3.10+
- `PySide6` (for the graphical interface)
- `imageio` (for image handling)
- `numpy` (for numerical operations)
- `Pillow` (for image processing)

You can install the required dependencies with:

```bash
pip install -r requirements.txt
```

Here's the `requirements.txt` content for the dependencies:

```
PySide6
imageio
numpy
Pillow
```

## Features

- Real-time communication with the NFC card server to fetch card details.
- Cards are generated dynamically in the GUI from JSON data received from the server.
- Animations and transitions are used to display the card in an engaging and smooth manner.
- Supports customizations for card appearance, fonts, and background style.
- Display card information such as card name, type, description, and stats.
- Option to show various limitations based on card attributes (Set ID, Passcode, Copyright, etc.).
- Supports a loading static and animated backgrounds.

## How It Works

The application waits for JSON data from the [Yu-Gi-Oh! Card NFC Server](https://github.com/SideswipeeZ/ygo-nfc-card-server). Once the server sends the card data, the viewer generates the card in the GUI with the following steps:

1. **JSON Data Reception**: The viewer listens for incoming JSON data from the server, which contains information about the card, including its attributes, image URL, lore, and other details.
   
2. **Dynamic Card Generation**: Once the card data is received, the app generates the card dynamically. This includes displaying card images, text (name, lore, etc.), and stats (ATK, DEF, type, etc.).

3. **Card Animation**: The card is animated into the view with smooth transitions. This includes fade-ins, slide-ins, and other transitions to make the card reveal more engaging. The transitions are handled within the GUI itself using PySide6.

4. **Limitations**: If enabled via command-line arguments, the application will display any card limitations based on the card's Set ID, Passcode, Copyright, Sticker, or Edition.

5. **Background and Appearance Customization**: The app allows for customization of the fonts used for different sections (title, lore, main text, links), as well as an option for a static background instead of dynamic ones.

## Usage

### Starting the Application

First, ensure that the [Yu-Gi-Oh! Card NFC Server](https://github.com/SideswipeeZ/ygo-nfc-card-server) is running and accessible. Then, run the following command to start the Yu-Gi-Oh! Card Viewer:

```bash
python card_viewer.py --server-address <server_address> --server-port <server_port>
```

- Replace `<server_address>` with the address of the NFC server (e.g., `localhost`).
- Replace `<server_port>` with the port on which the NFC server is running (default is `41112`).

For example:

```bash
python card_viewer.py --server-address localhost --server-port 41112
```

### Command-Line Arguments

The application accepts the following command-line arguments to customize its behavior:

#### Card Limitations (Optional Flags)

- `--show-limitations-setid`: Show limitations based on Set ID.
- `--show-limitations-passcode`: Show limitations based on Passcode.
- `--show-limitations-copyright`: Show limitations based on Copyright.
- `--show-limitations-sticker`: Show limitations based on Sticker.
- `--show-limitations-edition`: Show limitations based on Edition.

#### Background and Appearance

- `--static`: Load the static background version of the app (no dynamic backgrounds).
  
#### Port Configuration

- `--port <port_number>`: Specify the port number for connecting to the NFC server (default: `41112`).

#### Font Override Options

By Default these are the fonts that should work with the application. Make sure you have these fonts installed.

  -  "MatrixRegularSmallCaps" - Used for the Title and Stats
  -  "Stone Serif ITC Medium" - USed for the Card Lore
  -  "ITC Stone Serif" - Used for the main texts
  -  "EurostileCandyW01" - USed for the Link Rating


- `--title_font <font_path>`: Override the font used for the title text.
- `--lore_font <font_path>`: Override the font used for the lore text.
- `--main_font <font_path>`: Override the font used for main text.
- `--link_font <font_path>`: Override the font used for link text.

### Example Usage

Here are some examples.
To run the application with a custom font:

```bash
python card_viewer.py --server-address localhost --server-port 41112 --static --main_font "Arial"
```

To show card limitations based on Set ID:

```bash
python card_viewer.py --server-address localhost --server-port 41112 --show-limitations-setid
```

### Controls

Once the viewer is running:

- **Scan Card**: Place a Yu-Gi-Oh! card with an NFC tag near your reader. The viewer will automatically fetch the card's details and display them in the GUI. Once the card is detected or removed it will show.


### Customizing the Server Address and Port

You can specify a custom address and port for the NFC server when running the viewer:

```bash
python card_viewer.py --server-address localhost --server-port 41112
```

By default, the viewer will try to connect to `localhost` on port `41112`.

## How It Works

This viewer communicates with the Yu-Gi-Oh! Card NFC Server to retrieve card information. When an NFC tag is scanned, the viewer waits for JSON data from the server, which contains the card's details. The viewer then generates the card dynamically in the GUI, applying animations and transitions to display the card in an engaging manner. The viewer supports showing card limitations based on attributes and customizing the appearance of the GUI.

## License

This project is licensed under the GPL 3.0 License - see the [LICENSE](LICENSE) file for details.