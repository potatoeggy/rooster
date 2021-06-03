# rooster

Ensure that either [Mozilla Firefox](https://www.mozilla.org/en-US/firefox/) and [geckodriver](https://github.com/mozilla/geckodriver) or [Google Chrome](https://www.google.com/chrome/) and a `csc`-patched [chromedriver](https://chromedriver.chromium.org/) are installed.

**WARNING:** It is critical that a `csc` patched chromedriver is used as otherwise Google will block you. To patch the binary, perform a find and replace of all `csc_` strings and replace them with a different three-character string, e.g., `dog_`.

Install dependencies:

```
pip3 install --requirement requirements.txt
```
