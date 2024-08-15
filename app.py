import requests
import pprint
from flask import Flask, request, jsonify, render_template
import uuid
from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)

from bs4 import BeautifulSoup

base_url = "https://parivahan.gov.in"

url = "https://parivahan.gov.in/rcdlstatus/?pur_cd=101"

post_url = "https://parivahan.gov.in/rcdlstatus/vahan/rcDlHome.xhtml"

dl_sessions = {}

def get_data_from_tables(soup):
    data = []
    tables = soup.find_all("table")
    
    for table in tables:
        table_data = {
            "headers": [],
            "data": [],
        }

        thead = table.find("thead")
        if thead is not None:
            ths = thead.find_all("th")
            headers = []
            for th in ths:
                headers.append(th.text)
            table_data["headers"] = headers

        trs = table.find_all("tr")

        for tr in trs:
            row_data = []
            tds = tr.find_all("td")
            for i in range(len(tds)):
                row_data.append(tds[i].text)
            table_data["data"].append(row_data)

        data.append(table_data)
    return data


class DL:
    def __init__(self):
        self.post_data = {
            "avax.faces.partial.ajax": "true",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "form_rcdl:pnl_show form_rcdl:pg_show form_rcdl:rcdl_pnl",
        }
        self.base_url = "https://parivahan.gov.in"
        self.captcha_url = None
        self.page = None
        self.soup = None
        self.id = str(uuid.uuid4())
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Content-Type": "application/x-www-form-urlencoded",
        }   

    def initialise(self):
        self.page = self.session.get(url)
        self.soup = BeautifulSoup(self.page.content, "html.parser")
        self.get_default_inputs()

    def get_captcha_url(self):
        # Get the table with class vahan-captcha
        captcha_table = self.soup.find("table", {"class": "vahan-captcha"})
        # Get the img tag
        img = captcha_table.find("img")
        # Get the src attribute
        src = img["src"]
        self.captcha_url = self.base_url + src
        return self.captcha_url

    def get_default_inputs(self):
        form = self.soup.find("form", id="form_rcdl")
        inputs = form.find_all("input")
        print(len(inputs))
        for i in inputs:
            name = ""
            value = ""
            if i.has_attr("name"):
                name = i["name"]
            if i.has_attr("value"):
                value = i["value"]
            if name != "" and value != "":
                self.post_data[name] = value

        buttons = form.find_all('button')
        submitBtnName = buttons[1].get('name')

        self.post_data[submitBtnName] = submitBtnName
        self.post_data['javax.faces.source'] = submitBtnName

        self.captchaInputName = inputs[3].get('name')


@app.route("/api/get-captcha", methods=["GET"])
def get_captcha():
    try:
        dl = DL()
        dl.initialise()
        captchaSrc = dl.get_captcha_url()
        dl_sessions[dl.id] = dl
        return jsonify({"captcha": captchaSrc, "id": dl.id, "param": dl.post_data})
    
    except Exception as e:
        print(e)
        return jsonify({"error": "Error getting captcha"})


@app.route("/api/get-vehicle-details", methods=["POST"])
def get_vehicle_details():
    try:
        data = request.json
        id = data["sessionId"]
        dl = dl_sessions[id]
        dl.post_data["form_rcdl:tf_dlNO"] = data["dlno"]
        date = data["dob"]
        print(date)

        # date comes in formay yyyy-mm-dd
        # we need to convert it to dd-mm-yyyy
        date = date.split("-")
        date = date[2] + "-" + date[1] + "-" + date[0]
        print(date)

        dl.post_data["form_rcdl:tf_dob_input"] = date
        dl.post_data[dl.captchaInputName] = data["captchaData"]
        response = dl.session.post(post_url, data=dl.post_data)

        soup = BeautifulSoup(response.content, "html.parser")

        # print(soup)

        error_messages = []
        try:
            # Find a div with class ui-messages-error-summary
            errors = soup.find_all("span", {"class": "ui-messages-error-summary"})
            # print(errors)
            for error in errors:
                if error.text:
                    error_messages.append(error.text)

        except:
            print("Error getting error messages")

        print(error_messages)

        if len(error_messages) > 0:
            return jsonify({"errors": error_messages})

        details = None
        try:
            # Find a div with id form_rcdl:pnl_show
            details = soup.find("div", {"id": "form_rcdl:pnl_show"})
        except:
            pass

        if details is None:
            return jsonify({"error": "Error getting vehicle details"})

        # print(str(details))
        del dl_sessions[id]
        return jsonify({"details": get_data_from_tables(details)})
    except Exception as e:
        print(e)
        # close session object
        del dl_sessions[id]

        return jsonify({"error": str(e)})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(asgi_app, host='0.0.0.0', port=5001)