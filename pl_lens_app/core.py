import os
from datetime import datetime

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fhirpathpy import evaluate
from groq import Groq
from ollama import Client
from openai import OpenAI

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL")
MODEL_URL = os.getenv("MODEL_URL")
OPENAIKEY = os.getenv("OPENAI_KEY")
GROQAPIKEY = os.getenv("GROQ_API_KEY")

print(MODEL_URL)
if MODEL_URL is not None:
    client = Client(host=MODEL_URL)

if OPENAIKEY is not None:
    openaiclient = OpenAI(
        # This is the default and can be omitted
        api_key=OPENAIKEY
    )
if GROQAPIKEY is not None:
    groqclient = Groq(api_key=GROQAPIKEY)

LANGUAGE_MAP = {
    "es": "Spanish",
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "tr": "Turkish",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "vi": "Vietnamese",
    "th": "Thai",
    "el": "Greek",
    "cs": "Czech",
    "hu": "Hungarian",
    "ro": "Romanian",
    "sv": "Swedish",
    "fi": "Finnish",
    "da": "Danish",
    "no": "Norwegian",
    "is": "Icelandic",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mt": "Maltese",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "bg": "Bulgarian",
    "cy": "Welsh",
    "ga": "Irish",
    "gd": "Gaelic",
    "eu": "Basque",
    "ca": "Catalan",
    "gl": "Galician",
}


def create_extensions(epibundle, responses, classfound):
    for idx, response in enumerate(responses):
        #   print(response)
        epibundle["entry"][0]["resource"]["extension"].append(
            {
                "extension": [
                    {
                        "url": "elementClass",
                        "valueString": "plain-language-lens-" + str(idx),
                    },
                    {
                        "url": "type",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://hl7.eu/fhir/ig/gravitate-health/CodeSystem/type-of-data-cs",
                                    "code": "TXT",
                                    "display": "Text",
                                }
                            ]
                        },
                    },
                    {"url": "concept", "valueString": response},
                ],
                "url": "http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/AdditionalInformation",
            }
        )
    nidx = 0

    for ep in epibundle["entry"][0]["resource"]["section"][0]["section"]:
        soup = BeautifulSoup(ep["text"]["div"], "html.parser")
        element = soup.find(class_=classfound)
        if element:
            # Add the new class to the existing classes
            element["class"] = element.get("class", []) + [
                "plain-language-lens-" + str(nidx)
            ]
            nidx += 1

            # Update the original HTML content with the modified BeautifulSoup object
            ep["text"]["div"] = str(soup)
    return epibundle


def process_bundle_extensions(bundle):
    # Composition.name.where(use='usual').given.first()
    class_to_look_for = evaluate(
        bundle,
        "Bundle.entry[0].resource.extension.where(url='http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/HtmlElementLink').where(extension.valueCodeableReference.concept.coding.code='1' and extension.valueCodeableReference.concept.coding.system='http://hl7.eu/fhir/ig/gravitate-health/CodeSystem/tags' ).extension.where(url='elementClass').valueString",
        [],
    )
    #  print(mp)
    language = bundle["language"]
    # print(epi)
    data_to_explain = []
    idx = 0

    for ep in bundle["entry"][0]["resource"]["section"][0]["section"]:
        idx += 1

        # for v in ep["text"]["div"]:
        print(idx, "----", ep["text"]["div"])
        soup = BeautifulSoup(ep["text"]["div"], "html.parser")
        element = soup.find(class_=class_to_look_for)
        if element:
            element_text = element.get_text()
            print(f'Text content of the element with class "{class_to_look_for}":')
            print(element_text)
            data_to_explain.append(element_text)

    return language, data_to_explain, class_to_look_for


def process_ips(ips):
    pat = evaluate(ips, "Bundle.entry.where(resource.resourceType=='Patient')", [])[0][
        "resource"
    ]

    gender = pat["gender"]
    bd = pat["birthDate"]

    # Convert the string to a datetime object
    birth_date = datetime.strptime(bd, "%Y-%m-%d")

    # Get the current date
    current_date = datetime.now()

    # Calculate the age
    age = (
        current_date.year
        - birth_date.year
        - ((current_date.month, current_date.day) < (birth_date.month, birth_date.day))
    )
    conditions = evaluate(
        ips, "Bundle.entry.where(resource.resourceType=='Condition')", []
    )
    diagnostics = []
    # print(conditions)

    if conditions:
        for cond in conditions:
            diagnostics.append(cond["resource"]["code"]["coding"][0]["display"])

    medications = evaluate(
        ips, "Bundle.entry.where(resource.resourceType=='Medication')", []
    )
    meds = []
    for med in medications:
        meds.append(med["resource"]["code"]["coding"][0]["display"])

    return gender, age, diagnostics, meds


def parse_response_split(response):
    nresp = []
    for r in response.split("|"):
        if r.strip() != "":
            nresp.append(r.strip())

    return nresp


def explaining_plain_language(
    language, data_to_explain, age, diagnostics, medications, model
):
    lang = LANGUAGE_MAP[language]

    diagnostics_texts = ""

    if diagnostics:
        diagnostics_texts = "with the following diagnostics "
        for diag in diagnostics:
            diagnostics_texts += diag + ", "

    else:
        diagnostics_texts = "without any diagnostics"
    piped_sentences = "|".join(data_to_explain)
    prompt = f"Please simplify the following technical health information into plain language suitable for a {age}-year-old. Each piece of information is separated by '|'. Provide the simplified explanation for each piece of information in the same order, using the same delimiter '|'. Ensure the explanations are clear, concise, and easy to understand.\n\nOriginal: {piped_sentences}\nAnswer:"
    if "llama3" in model:
        systemMessage = (
            """You are an AI assistant specialized in simplifying technical health information for different age groups. Your task is to read complex medical sentences separated by a delimiter and rewrite them in simple language appropriate for the specified age. Each piece of information is separated by a '|' character. Maintain the structure and format in your response, ensuring each simplified sentence is also separated by '|'.\n
        You must follow this indications extremety strictly:\n
        1. You must answer in """
            + lang
            + """ \n

        """
        )

        print("prompt is:" + prompt)

        prompt_message = prompt
        result = client.chat(
            model="llama3",
            messages=[
                {"content": systemMessage, "role": "system"},
                {"content": prompt_message, "role": "assistant"},
            ],
            stream=False,
            keep_alive="-1m",
        )

        response = result["message"]["content"]
        print(response)
        # print(response.split("|"))

        parsed_response = parse_response_split(response)
        if len(parsed_response) != len(data_to_explain):
            errormessage = (
                "Error: The number of responses does not match the number of inputs",
                len(parsed_response),
                len(data_to_explain),
            )
            raise Exception(errormessage)
    return {
        "response": parsed_response,
        "prompt": prompt,
        "datetime": datetime.now(),
        "model": model,
    }
