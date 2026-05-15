
# ---------------- MEDICINE ----------------
@app.route("/medicine", methods=["GET", "POST"])
def medicine():

    if "user" not in session:
        return redirect("/signin")

    suggestion = ""
    symptom = ""

    if request.method == "POST":

        problem = request.form["problem"].lower()

        if "fever" in problem:
            suggestion = "Take rest and drink fluids"
            symptom = "Summer"

        elif "cold" in problem:
            suggestion = "Steam inhalation recommended"


        elif "headache" in problem:
            suggestion = "Take proper rest"


        else:
            suggestion = "Consult a doctor"


        # ---------------- SAVE HISTORY ----------------
        current_time = datetime.now().strftime("%d-%m-%Y %I:%M %p")

        data = {
            "user": session["user"],
            "problem": problem,
            "suggestion": suggestion,
            "symptom" : symptom,
            "time": current_time
        }

        if os.path.exists("medicine_data.json"):

            with open("medicine_data.json", "r") as f:
                all_data = json.load(f)

        else:
            all_data = []

        all_data.append(data)

        with open("medicine_data.json", "w") as f:
            json.dump(all_data, f, indent=4)

    return render_template(
        "medicine.html",
        suggestion=suggestion,
        symptom=symptom
    )

# ---------------- MEDICINE ----------------
@app.route("/medicine", methods=["GET", "POST"])
def medicine():

    if "user" not in session:
        return redirect("/signin")

    suggestion = ""
    symptom = ""

    if request.method == "POST":

        problem = request.form["problem"].lower()

        suggestion = "Consult a doctor"

        # OPEN JSON FILE
        with open("medicine_database.json", "r") as file:

            database = json.load(file)

        # CHECK ALL SYMPTOMS
        for item in database:

            for s in item["problems"]:

                if s.lower() in symptom:

                    suggestion = ", ".join(item["suggestions"])
                    symptom = ", ".join(item["symptoms"])

                    break

        # SAVE HISTORY
        current_time = datetime.now().strftime("%d-%m-%Y %I:%M %p")

        data = {
            "user": session["user"],
            "problem": problem,
            "symptom": symptom,
            "suggestion": suggestion,
            "time": current_time
        }

        if os.path.exists("medicine_data.json"):

            with open("medicine_data.json", "r") as f:
                all_data = json.load(f)

        else:
            all_data = []

        all_data.append(data)

        with open("medicine_data.json", "w") as f:
            json.dump(all_data, f, indent=4)

    return render_template(
        "medicine.html",
        suggestion=suggestion,
        symptom=symptom
    )