FormSmarts PDF Downloader
==========================

This tool downloads the PDF version of your submitted forms, for a
form and date range you choose, into a folder on your computer.


INSTALLATION
------------

1. Copy this whole "pdf_downloader" folder anywhere on your computer
   (for example, your Desktop or Documents folder).

2. Open the folder, then open the "windows" folder inside it, and
   double-click:

       install.bat

3. A black window will open and set things up automatically:
   - It installs Python if your computer doesn't already have it.
   - It installs the software this tool needs (nothing is installed
     system-wide -- it's all kept in its own private folder).
   - It creates a shortcut named "FormSmarts PDF Downloader" on your
     Desktop.
   - It will ask if you want to enter your download folder and API
     key now -- type Y and press Enter.

4. When it's done, you can close the window. From now on, use the
   "FormSmarts PDF Downloader" shortcut on your Desktop to run the
   tool.

You can run install.bat again at any time -- for example if something
needs updating. It won't lose your saved settings.


FIRST-TIME SETUP / CHANGING YOUR SETTINGS
------------------------------------------

Run the "FormSmarts PDF Downloader" shortcut and add --configure after
it (or just answer Y when install.bat asks). You'll be asked for:

  Download directory
      Where PDFs are saved on your computer.

  Account ID
      Your FormSmarts account ID (looks like FSA-123456). You can find
      this under Account Overview in your FormSmarts account.

  API Key
      Found under Security Settings in your FormSmarts account. This
      is saved using Windows' built-in secure credential storage --
      it is never written to a plain file. If your computer doesn't
      support this for some reason, the key won't be saved at all,
      and you'll be asked for it each time you run the tool.


EVERYDAY USE
------------

Double-click the "FormSmarts PDF Downloader" shortcut on your Desktop.
(If you skipped setup earlier, it will walk you through it automatically
the first time you do this.) It will ask you three questions:

    Form ID:
    Start date (YYYY-MM-DD):
    End date (YYYY-MM-DD):

Your PDFs will be saved into a new folder named after the form and the
dates you chose, for example:

    <your download folder>\lqh_2026-01-01_to_2026-01-31\

If you run the tool again for the same form and dates, it will skip
any PDFs it already downloaded, so it's safe to run again later to
pick up new submissions.

The tool pauses briefly between each download so it doesn't overload
FormSmarts' servers -- this is normal and expected.


RUNNING ON A MAC OR LINUX COMPUTER (ADVANCED / DEVELOPERS)
----------------------------------------------------------

The Windows install steps above don't apply on a Mac. Instead, open
Terminal, go to this folder, and run:

    cd path/to/pdf_downloader
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    python -m formsmarts_pdf_downloader --configure   (one-time setup)
    python -m formsmarts_pdf_downloader                (everyday use)

The API key is saved to the macOS Keychain, and the download folder /
account ID are saved to:

    ~/Library/Application Support/FormSmartsPDFDownloader/config.json

Note: run it as "python -m formsmarts_pdf_downloader", not
"python cli.py" -- it needs to be run as a package from this folder.


UNINSTALLING
------------

Open the "windows" folder inside "pdf_downloader" and double-click:

    uninstall.bat

This removes the application, your saved settings (download folder,
account ID), your saved API key, and the Desktop shortcut. It will ask
you to confirm first. PDFs you've already downloaded are NOT deleted --
they stay in whatever download folder you configured.


NEED HELP?
----------

If anything goes wrong, note down the exact message shown in the
black window and send it to FormSmarts support 
(https://formsmarts.com/form-builder-support#contact).
