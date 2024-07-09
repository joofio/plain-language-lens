from flask import request, jsonify
from pl_lens_app import app
import requests
from pl_lens_app.core import (
    SERVER_URL,
    process_bundle_extensions,
    process_ips,
    explaining_plain_language,
    create_extensions,
)


print(app.config)


@app.route("/", methods=["GET"])
def hello():
    json_obj = {
        "message": "Hello and welcome to the Plain Language Lens API",
        "status": "OK",
    }
    return jsonify(json_obj)


@app.route("/plain-language", methods=["POST"])
@app.route("/plain-language/<bundleid>", methods=["GET", "POST"])
def lens_app(bundleid=None):
    epibundle = None
    ips = None
    # Get the query parameters from the request
    preprocessor = request.args.get("preprocessors", "")
    lenses = request.args.get("lenses", "")
    patientIdentifier = request.args.get("patientIdentifier", "")
    model = request.args.get("model", "")
    print(preprocessor, lenses, patientIdentifier, model)
    if lenses not in ["plain-language-lens"]:
        return "Error: lens not supported", 404
    if preprocessor not in ["preprocessing-service-manual"]:
        return "Error: preprocessor not supported", 404

    if request.method == "GET":
        if preprocessor == "" or lenses == "" or patientIdentifier == "":
            return "Error: missing parameters", 404

    print(SERVER_URL)
    if request.method == "POST":
        data = request.json
        epibundle = data.get("epi")
        ips = data.get("ips")
        #  print(epibundle)
        if ips is None and patientIdentifier == "":
            return "Error: missing IPS data", 404
        # preprocessed_bundle, ips = separate_data(bundleid, patientIdentifier)
        if epibundle is None and bundleid is None:
            return "Error: missing EPI data", 404

    if epibundle is None:
        print("epibundle is none")
        # print(epibundle)
        # print(bundleid)
        print(SERVER_URL + "epi/api/fhir/Bundle/" + bundleid)
        #   print(ips)
        epibundle = requests.get(SERVER_URL + "epi/api/fhir/Bundle/" + bundleid).json()
    # print(epibundle)
    language, data_to_explain, classfound = process_bundle_extensions(epibundle)
    print(language, data_to_explain, classfound)
    print(SERVER_URL)
    if ips is None:
        # print(ips)
        ips = requests.get(
            SERVER_URL + "ips/api/fhir/Patient/$summary?identifier=" + patientIdentifier
        ).json()
    # print(ips)
    # print(ips)
    gender, age, diagnostics, medications = process_ips(ips)

    response = explaining_plain_language(
        language, data_to_explain, age, diagnostics, medications, model
    )
    newbundle = create_extensions(epibundle, response["response"], classfound)

    newbundle["entry"][0]["resource"]["category"][0] = {
        "coding": [
            {
                "system": "http://hl7.eu/fhir/ig/gravitate-health/CodeSystem/epicategory-cs",
                "code": "F",
                "display": "Focused",
            }
        ]
    }

    return jsonify(newbundle)
