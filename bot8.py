
==> Cloning from https://github.com/rosalexxi/telegram-bot-nutricion
==> Checking out commit 13f1829a62792bcc4a01aa0810377201b5de9ae7 in branch main
==> Downloaded 97MB in 2s. Extraction took 1s.
==> Using Python version 3.12.8 via environment variable PYTHON_VERSION
==> Docs on specifying a Python version: https://render.com/docs/python-version
==> Installing Python version 3.12.8...
==> Using Poetry version 2.1.3 (default)
==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
==> Running build command 'pip install -r requirements.txt'...
Collecting python-telegram-bot>=20.0 (from -r requirements.txt (line 1))
  Using cached python_telegram_bot-22.8-py3-none-any.whl.metadata (17 kB)
Collecting groq>=0.4.0 (from -r requirements.txt (line 2))
  Using cached groq-1.6.0-py3-none-any.whl.metadata (16 kB)
Collecting pandas>=2.0.0 (from -r requirements.txt (line 3))
  Using cached pandas-3.0.5-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl.metadata (79 kB)
Collecting openpyxl>=3.0.0 (from -r requirements.txt (line 4))
  Using cached openpyxl-3.1.5-py2.py3-none-any.whl.metadata (2.5 kB)
Collecting python-dotenv>=1.0.0 (from -r requirements.txt (line 5))
  Using cached python_dotenv-1.2.2-py3-none-any.whl.metadata (27 kB)
Collecting gspread>=5.10.0 (from -r requirements.txt (line 6))
  Using cached gspread-6.2.1-py3-none-any.whl.metadata (11 kB)
Collecting google-auth>=2.20.0 (from -r requirements.txt (line 7))
  Using cached google_auth-2.56.2-py3-none-any.whl.metadata (6.0 kB)
Collecting pytz>=2023.3 (from -r requirements.txt (line 8))
  Using cached pytz-2026.3.post1-py2.py3-none-any.whl.metadata (22 kB)
Collecting flask>=3.0.0 (from -r requirements.txt (line 9))
  Using cached flask-3.1.3-py3-none-any.whl.metadata (3.2 kB)
Collecting reportlab>=4.0.0 (from -r requirements.txt (line 10))
  Using cached reportlab-5.0.0-py3-none-any.whl.metadata (1.6 kB)
Collecting gunicorn>=21.2.0 (from -r requirements.txt (line 11))
  Using cached gunicorn-26.0.0-py3-none-any.whl.metadata (5.4 kB)
Collecting requests>=2.31.0 (from -r requirements.txt (line 12))
  Using cached requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting pydantic>=2.7.0 (from -r requirements.txt (line 13))
  Using cached pydantic-2.13.4-py3-none-any.whl.metadata (109 kB)
Collecting httpx<0.29,>=0.27 (from python-telegram-bot>=20.0->-r requirements.txt (line 1))
  Using cached httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
Collecting anyio<5,>=3.5.0 (from groq>=0.4.0->-r requirements.txt (line 2))
  Using cached anyio-4.14.2-py3-none-any.whl.metadata (4.6 kB)
Collecting distro<2,>=1.7.0 (from groq>=0.4.0->-r requirements.txt (line 2))
  Using cached distro-1.9.0-py3-none-any.whl.metadata (6.8 kB)
Collecting sniffio (from groq>=0.4.0->-r requirements.txt (line 2))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting typing-extensions<5,>=4.14 (from groq>=0.4.0->-r requirements.txt (line 2))
  Using cached typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting numpy>=1.26.0 (from pandas>=2.0.0->-r requirements.txt (line 3))
  Using cached numpy-2.5.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (6.6 kB)
Collecting python-dateutil>=2.8.2 (from pandas>=2.0.0->-r requirements.txt (line 3))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting et-xmlfile (from openpyxl>=3.0.0->-r requirements.txt (line 4))
  Using cached et_xmlfile-2.0.0-py3-none-any.whl.metadata (2.7 kB)
Collecting google-auth-oauthlib>=0.4.1 (from gspread>=5.10.0->-r requirements.txt (line 6))
  Using cached google_auth_oauthlib-1.4.0-py3-none-any.whl.metadata (2.6 kB)
Collecting pyasn1-modules>=0.2.1 (from google-auth>=2.20.0->-r requirements.txt (line 7))
  Using cached pyasn1_modules-0.4.2-py3-none-any.whl.metadata (3.5 kB)
Collecting cryptography>=38.0.3 (from google-auth>=2.20.0->-r requirements.txt (line 7))
  Using cached cryptography-50.0.0-cp311-abi3-manylinux_2_34_x86_64.whl.metadata (4.3 kB)
Collecting blinker>=1.9.0 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached blinker-1.9.0-py3-none-any.whl.metadata (1.6 kB)
Collecting click>=8.1.3 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached click-8.4.2-py3-none-any.whl.metadata (2.6 kB)
Collecting itsdangerous>=2.2.0 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached itsdangerous-2.2.0-py3-none-any.whl.metadata (1.9 kB)
Collecting jinja2>=3.1.2 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting markupsafe>=2.1.1 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.7 kB)
Collecting werkzeug>=3.1.0 (from flask>=3.0.0->-r requirements.txt (line 9))
  Using cached werkzeug-3.1.8-py3-none-any.whl.metadata (4.0 kB)
Collecting pillow>=9.0.0 (from reportlab>=4.0.0->-r requirements.txt (line 10))
  Using cached pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (9.1 kB)
Collecting charset-normalizer (from reportlab>=4.0.0->-r requirements.txt (line 10))
  Using cached charset_normalizer-3.4.9-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (41 kB)
Collecting packaging (from gunicorn>=21.2.0->-r requirements.txt (line 11))
  Using cached packaging-26.2-py3-none-any.whl.metadata (3.5 kB)
Collecting idna<4,>=2.5 (from requests>=2.31.0->-r requirements.txt (line 12))
  Using cached idna-3.18-py3-none-any.whl.metadata (6.1 kB)
Collecting urllib3<3,>=1.26 (from requests>=2.31.0->-r requirements.txt (line 12))
  Using cached urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
Collecting certifi>=2023.5.7 (from requests>=2.31.0->-r requirements.txt (line 12))
  Using cached certifi-2026.7.22-py3-none-any.whl.metadata (2.5 kB)
Collecting annotated-types>=0.6.0 (from pydantic>=2.7.0->-r requirements.txt (line 13))
  Using cached annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.4 (from pydantic>=2.7.0->-r requirements.txt (line 13))
  Using cached pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
Collecting typing-inspection>=0.4.2 (from pydantic>=2.7.0->-r requirements.txt (line 13))
  Using cached typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
Collecting cffi>=2.0.0 (from cryptography>=38.0.3->google-auth>=2.20.0->-r requirements.txt (line 7))
  Using cached cffi-2.1.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (2.5 kB)
Collecting requests-oauthlib>=0.7.0 (from google-auth-oauthlib>=0.4.1->gspread>=5.10.0->-r requirements.txt (line 6))
  Using cached requests_oauthlib-2.0.0-py2.py3-none-any.whl.metadata (11 kB)
Collecting httpcore==1.* (from httpx<0.29,>=0.27->python-telegram-bot>=20.0->-r requirements.txt (line 1))
  Using cached httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx<0.29,>=0.27->python-telegram-bot>=20.0->-r requirements.txt (line 1))
  Using cached h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting pyasn1<0.7.0,>=0.6.1 (from pyasn1-modules>=0.2.1->google-auth>=2.20.0->-r requirements.txt (line 7))
  Using cached pyasn1-0.6.4-py3-none-any.whl.metadata (8.4 kB)
Collecting six>=1.5 (from python-dateutil>=2.8.2->pandas>=2.0.0->-r requirements.txt (line 3))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting pycparser (from cffi>=2.0.0->cryptography>=38.0.3->google-auth>=2.20.0->-r requirements.txt (line 7))
  Using cached pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
Collecting oauthlib>=3.0.0 (from requests-oauthlib>=0.7.0->google-auth-oauthlib>=0.4.1->gspread>=5.10.0->-r requirements.txt (line 6))
  Using cached oauthlib-3.3.1-py3-none-any.whl.metadata (7.9 kB)
Using cached python_telegram_bot-22.8-py3-none-any.whl (769 kB)
Using cached groq-1.6.0-py3-none-any.whl (143 kB)
Using cached pandas-3.0.5-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl (11.0 MB)
Using cached openpyxl-3.1.5-py2.py3-none-any.whl (250 kB)
Using cached python_dotenv-1.2.2-py3-none-any.whl (22 kB)
Using cached gspread-6.2.1-py3-none-any.whl (59 kB)
Using cached google_auth-2.56.2-py3-none-any.whl (258 kB)
Using cached pytz-2026.3.post1-py2.py3-none-any.whl (508 kB)
Using cached flask-3.1.3-py3-none-any.whl (103 kB)
Using cached reportlab-5.0.0-py3-none-any.whl (2.0 MB)
Using cached gunicorn-26.0.0-py3-none-any.whl (212 kB)
Using cached requests-2.34.2-py3-none-any.whl (73 kB)
Using cached pydantic-2.13.4-py3-none-any.whl (472 kB)
Using cached pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
Using cached annotated_types-0.8.0-py3-none-any.whl (13 kB)
Using cached anyio-4.14.2-py3-none-any.whl (125 kB)
Using cached blinker-1.9.0-py3-none-any.whl (8.5 kB)
Using cached certifi-2026.7.22-py3-none-any.whl (136 kB)
Using cached charset_normalizer-3.4.9-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (224 kB)
Using cached click-8.4.2-py3-none-any.whl (119 kB)
Using cached cryptography-50.0.0-cp311-abi3-manylinux_2_34_x86_64.whl (4.7 MB)
Using cached distro-1.9.0-py3-none-any.whl (20 kB)
Using cached google_auth_oauthlib-1.4.0-py3-none-any.whl (19 kB)
Using cached httpx-0.28.1-py3-none-any.whl (73 kB)
Using cached httpcore-1.0.9-py3-none-any.whl (78 kB)
Using cached idna-3.18-py3-none-any.whl (65 kB)
Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Using cached jinja2-3.1.6-py3-none-any.whl (134 kB)
Using cached markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (22 kB)
Using cached numpy-2.5.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (16.7 MB)
Using cached pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (6.9 MB)
Using cached pyasn1_modules-0.4.2-py3-none-any.whl (181 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Using cached typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Using cached urllib3-2.7.0-py3-none-any.whl (131 kB)
Using cached werkzeug-3.1.8-py3-none-any.whl (226 kB)
Using cached et_xmlfile-2.0.0-py3-none-any.whl (18 kB)
Using cached packaging-26.2-py3-none-any.whl (100 kB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Using cached cffi-2.1.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (221 kB)
Using cached pyasn1-0.6.4-py3-none-any.whl (84 kB)
Using cached requests_oauthlib-2.0.0-py2.py3-none-any.whl (24 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Using cached oauthlib-3.3.1-py3-none-any.whl (160 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Installing collected packages: pytz, urllib3, typing-extensions, sniffio, six, python-dotenv, pycparser, pyasn1, pillow, packaging, oauthlib, numpy, markupsafe, itsdangerous, idna, h11, et-xmlfile, distro, click, charset-normalizer, certifi, blinker, annotated-types, werkzeug, typing-inspection, requests, reportlab, python-dateutil, pydantic-core, pyasn1-modules, openpyxl, jinja2, httpcore, gunicorn, cffi, anyio, requests-oauthlib, pydantic, pandas, httpx, flask, cryptography, python-telegram-bot, groq, google-auth, google-auth-oauthlib, gspread
Successfully installed annotated-types-0.8.0 anyio-4.14.2 blinker-1.9.0 certifi-2026.7.22 cffi-2.1.0 charset-normalizer-3.4.9 click-8.4.2 cryptography-50.0.0 distro-1.9.0 et-xmlfile-2.0.0 flask-3.1.3 google-auth-2.56.2 google-auth-oauthlib-1.4.0 groq-1.6.0 gspread-6.2.1 gunicorn-26.0.0 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 idna-3.18 itsdangerous-2.2.0 jinja2-3.1.6 markupsafe-3.0.3 numpy-2.5.1 oauthlib-3.3.1 openpyxl-3.1.5 packaging-26.2 pandas-3.0.5 pillow-12.3.0 pyasn1-0.6.4 pyasn1-modules-0.4.2 pycparser-3.0 pydantic-2.13.4 pydantic-core-2.46.4 python-dateutil-2.9.0.post0 python-dotenv-1.2.2 python-telegram-bot-22.8 pytz-2026.3.post1 reportlab-5.0.0 requests-2.34.2 requests-oauthlib-2.0.0 six-1.17.0 sniffio-1.3.1 typing-extensions-4.16.0 typing-inspection-0.4.2 urllib3-2.7.0 werkzeug-3.1.8
[notice] A new release of pip is available: 24.3.1 -> 26.2
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 3.4s. Compression took 1.1s
==> Build successful 🎉
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> Running 'python bot8.py'
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:10000
 * Running on http://10.30.184.194:10000
Press CTRL+C to quit
 * Serving Flask app 'bot8'
 * Debug mode: off
Traceback (most recent call last):
  File "/opt/render/project/src/bot8.py", line 1534, in <module>
    main()
  File "/opt/render/project/src/bot8.py", line 1522, in main
    application.add_handler(CommandHandler("presion", cmd_presion_handler))
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_handlers/commandhandler.py", line 143, in __init__
    raise ValueError(f"Command `{comm}` is not a valid bot command")
ValueError: Command `presion` is not a valid bot command
==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'python bot8.py'
 * Serving Flask app 'bot8'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:10000
 * Running on http://10.30.184.194:10000
Press CTRL+C to quit
Traceback (most recent call last):
  File "/opt/render/project/src/bot8.py", line 1534, in <module>
    main()
  File "/opt/render/project/src/bot8.py", line 1522, in main
    application.add_handler(CommandHandler("presion", cmd_presion_handler))
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_handlers/commandhandler.py", line 143, in __init__
    raise ValueError(f"Command `{comm}` is not a valid bot command")
ValueError: Command `presion` is not a valid bot command
