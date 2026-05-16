from flask import Flask, render_template, request, redirect, session
import json
import os
from datetime import datetime
import random
import string

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "medicare_secret"

USER_FILE = "users.json"

# ---------------- LOAD USERS ----------------
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

# ---------------- SAVE USERS ----------------
def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("device.html")


# ---------------- PC USER ----------------
@app.route("/device/pc")
def pc_user():

    session["mobile_user"] = False

    return render_template("auth.html")


# ---------------- MOBILE USER ----------------
@app.route("/device/mobile")
def mobile_user():

    session["mobile_user"] = True

    return render_template("auth.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        fullname = request.form["fullname"]
        dob = request.form["dob"]
        email = request.form["email"]

        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users:
            return "Username already exists"

        # SAVE TEMP USER
        session["temp_user"] = {
            "fullname": fullname,
            "dob": dob,
            "email": email,
            "username": username,

            "password": generate_password_hash(password)
        }

        # GENERATE HARD CAPTCHA
        characters = string.ascii_letters + string.digits + "@#$%&*"

        captcha = ''.join(random.choice(characters) for i in range(8))

        session["captcha"] = captcha

        return redirect("/verify_captcha")

    return render_template("signup.html")

# ---------------- SIGNIN ----------------
@app.route("/signin", methods=["GET", "POST"])
def signin():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users:

            saved_password = users[username]["password"]

            if check_password_hash(saved_password, password):

                session["user"] = username

                return redirect("/dashboard")

            else:
                return "Wrong Password"

        else:
            return "User Not Found"

    return render_template("signin.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/signin")

    return render_template(
        "dashboard.html",
        user=session["user"]
    )

# ---------------- HEALTH TIPS ----------------
@app.route("/healthtips")
def healthtips():

    if "user" not in session:
        return redirect("/signin")

    tips = [
         "1. Eat a balanced diet.",
    "2. Stay hydrated.",
    "3. Exercise regularly.",
    "4. Take regular breaks while working.",
    "5. Maintain proper posture.",
    "6. Wash hands before meals.",
    "7. Brush teeth twice daily.",
    "8. Get at least 7–8 hours of sleep.",
    "9. Avoid processed foods.",
    "10. Limit sugar intake.",
    "11. Drink enough water daily.",
    "12. Take short walks every hour.",
    "13. Avoid smoking.",
    "14. Limit alcohol consumption.",
    "15. Practice deep breathing exercises.",
    "16. Keep a positive mindset.",
    "17. Eat more fruits and vegetables.",
    "18. Avoid junk food.",
    "19. Include protein in your diet.",
    "20. Reduce salt intake.",
    "21. Practice mindfulness meditation.",
    "22. Stretch before and after exercise.",
    "23. Maintain a healthy weight.",
    "24. Wear sunscreen outdoors.",
    "25. Use ergonomic furniture.",
    "26. Avoid staring at screens for too long.",
    "27. Take breaks from phone and social media.",
    "28. Practice gratitude daily.",
    "29. Keep your living space clean.",
    "30. Avoid skipping meals.",
    "31. Eat fiber-rich foods.",
    "32. Maintain regular meal times.",
    "33. Limit caffeine intake.",
    "34. Keep a journal for mental health.",
    "35. Engage in hobbies regularly.",
    "36. Connect with friends and family.",
    "37. Listen to relaxing music.",
    "38. Avoid negative news overload.",
    "39. Take deep breaths during stress.",
    "40. Laugh often.",
    "41. Avoid excessive snacking.",
    "42. Walk or cycle instead of driving short distances.",
    "43. Practice yoga or stretching daily.",
    "44. Avoid unnecessary screen time before bed.",
    "45. Keep your mind active with reading or puzzles.",
    "46. Avoid processed meats.",
    "47. Include whole grains in diet.",
    "48. Avoid trans fats.",
    "49. Keep a balanced ratio of carbs, fats, and protein.",
    "50. Take vitamins if needed after consulting a doctor.",
    "51. Avoid over-eating.",
    "52. Practice portion control.",
    "53. Include omega-3 fatty acids in diet.",
    "54. Practice hand hygiene frequently.",
    "55. Cover mouth while coughing or sneezing.",
    "56. Avoid crowded places during flu season.",
    "57. Keep vaccinations up to date.",
    "58. Use mosquito repellents when needed.",
    "59. Avoid standing water to prevent mosquitoes.",
    "60. Keep first aid kit handy.",
    "61. Wear proper shoes while exercising.",
    "62. Maintain dental checkups regularly.",
    "63. Avoid sharing personal items.",
    "64. Keep hair clean and well-groomed.",
    "65. Wear clean clothes daily.",
    "66. Take care of your skin daily.",
    "67. Practice self-care routines.",
    "68. Stay connected socially.",
    "69. Engage in community activities.",
    "70. Volunteer occasionally.",
    "71. Avoid prolonged sitting.",
    "72. Maintain ergonomic work setup.",
    "73. Take eye breaks while working on screens.",
    "74. Blink frequently to prevent dry eyes.",
    "75. Avoid rubbing eyes excessively.",
    "76. Use moisturizer if needed.",
    "77. Keep nails trimmed and clean.",
    "78. Avoid nail-biting.",
    "79. Avoid touching face frequently.",
    "80. Maintain personal hygiene in public places.",
    "81. Use hand sanitizer when soap is not available.",
    "82. Clean frequently touched surfaces.",
    "83. Keep devices clean.",
    "84. Avoid texting while walking.",
    "85. Limit phone use before sleep.",
    "86. Practice meditation for mental clarity.",
    "87. Avoid stress accumulation.",
    "88. Delegate tasks when overwhelmed.",
    "89. Organize workspace for efficiency.",
    "90. Take short walks during breaks.",
    "91. Practice deep breathing exercises.",
    "92. Get sunlight exposure daily.",
    "93. Keep room well-ventilated.",
    "94. Avoid indoor pollution.",
    "95. Drink green tea occasionally.",
    "96. Include antioxidants in diet.",
    "97. Avoid excess oil consumption.",
    "98. Eat seasonal fruits.",
    "99. Avoid overuse of sugar.",
    "100. Monitor blood pressure regularly.",
    "101. Monitor blood sugar levels if at risk.",
    "102. Check cholesterol regularly.",
    "103. Get annual health checkups.",
    "104. Monitor BMI.",
    "105. Maintain a balanced diet chart.",
    "106. Keep a daily step count goal.",
    "107. Practice deep squats or light exercise.",
    "108. Avoid lifting heavy weights incorrectly.",
    "109. Stretch before intense exercises.",
    "110. Avoid prolonged exposure to cold or heat.",
    "111. Wear protective gear for sports.",
    "112. Follow traffic rules.",
    "113. Use seatbelts while driving.",
    "114. Avoid drinking and driving.",
    "115. Take breaks during long drives.",
    "116. Keep emergency contacts ready.",
    "117. Learn CPR basics.",
    "118. Practice mindfulness daily.",
    "119. Avoid negative self-talk.",
    "120. Celebrate small achievements.",
    "121. Avoid unhealthy comparisons.",
    "122. Get mental health counseling if stressed.",
    "123. Avoid isolation.",
    "124. Take regular vacations.",
    "125. Practice deep relaxation techniques.",
    "126. Laugh daily to reduce stress.",
    "127. Avoid excessive caffeine consumption.",
    "128. Limit screen time.",
    "129. Take frequent short breaks.",
    "130. Stay hydrated during workouts.",
    "131. Wear appropriate sportswear.",
    "132. Maintain safe workout environment.",
    "133. Track heart rate during exercise.",
    "134. Avoid skipping warm-up and cool-down.",
    "135. Practice breathing techniques during yoga.",
    "136. Include meditation for mental balance.",
    "137. Keep a positive daily affirmation.",
    "138. Avoid long periods of sitting.",
    "139. Stand up every hour.",
    "140. Walk during phone calls.",
    "141. Reduce junk food intake gradually.",
    "142. Include healthy fats in diet.",
    "143. Avoid fried foods.",
    "144. Eat home-cooked meals when possible.",
    "145. Avoid excessive eating outside.",
    "146. Track calories if needed.",
    "147. Eat slowly to aid digestion.",
    "148. Avoid overeating at night.",
    "149. Take probiotics if recommended.",
    "150. Include prebiotics and fiber.",
    "151. Drink warm water in mornings.",
    "152. Avoid sugary drinks.",
    "153. Replace sodas with water or herbal tea.",
    "154. Chew food properly.",
    "155. Avoid heavy meals late at night.",
    "156. Include vegetables in every meal.",
    "157. Eat fruits between meals.",
    "158. Avoid skipping breakfast.",
    "159. Have light dinners.",
    "160. Avoid high-calorie snacks.",
    "161. Limit salt intake.",
    "162. Include calcium-rich foods.",
    "163. Include iron-rich foods.",
    "164. Include vitamin D foods.",
    "165. Take supplements if necessary.",
    "166. Avoid taking too many supplements.",
    "167. Consult doctor before starting supplements.",
    "168. Avoid fad diets.",
    "169. Follow balanced nutrition.",
    "170. Avoid highly processed foods.",
    "171. Include omega-3 fatty acids.",
    "172. Limit fast food intake.",
    "173. Choose healthy cooking methods.",
    "174. Prefer steaming or grilling.",
    "175. Avoid overcooked food.",
    "176. Avoid burnt food.",
    "177. Use herbs and spices instead of salt.",
    "178. Avoid excessive sugar in tea or coffee.",
    "179. Avoid sugary desserts frequently.",
    "180. Practice mindful eating.",
    "181. Drink green smoothies occasionally.",
    "182. Include nuts and seeds in diet.",
    "183. Eat whole fruits instead of juice.",
    "184. Limit processed snacks.",
    "185. Choose whole grains over refined grains.",
    "186. Avoid white bread frequently.",
    "187. Include lentils and beans in meals.",
    "188. Use olive oil or coconut oil for cooking.",
    "189. Avoid excessive fried food.",
    "190. Include yogurt in diet.",
    "191. Take a multivitamin if needed.",
    "192. Keep a food diary for tracking.",
    "193. Avoid emotional eating.",
    "194. Reduce stress-related snacking.",
    "195. Limit late-night snacking.",
    "196. Plan meals ahead to avoid unhealthy choices.",
    "197. Include seasonal vegetables daily.",
    "198. Celebrate small victories.",
    "199. Avoid excessive social media time.",
    "200. Spend time in nature.",
    "201. Practice deep breathing exercises daily.",
    "202. Avoid multitasking constantly.",
    "203. Prioritize sleep over late-night work.",
    "204. Avoid sleeping with lights on.",
    "205. Maintain a sleep schedule.",
    "206. Avoid screens before bed.",
    "207. Keep bedroom cool and dark for sleep.",
    "208. Take short naps if needed.",
    "209. Avoid napping late in the day.",
    "210. Limit caffeine after noon.",
    "211. Maintain mental relaxation routines.",
    "212. Practice progressive muscle relaxation.",
    "213. Include mindfulness activities.",
    "214. Practice yoga or stretching.",
    "215. Walk outdoors regularly.",
    "216. Avoid long sedentary periods.",
    "217. Stand up and stretch every hour.",
    "218. Take short walks after meals.",
    "219. Avoid excessive sitting at work.",
    "220. Use stairs instead of elevator when possible.",
    "221. Limit elevator use for short distances.",
    "222. Wear comfortable shoes for walking.",
    "223. Include cardio exercise thrice a week.",
    "224. Include strength training twice a week.",
    "225. Warm-up before exercise.",
    "226. Cool down after exercise.",
    "227. Stay hydrated during workouts.",
    "228. Avoid overtraining.",
    "229. Listen to your body.",
    "230. Take rest days for recovery.",
    "231. Practice balance exercises.",
    "232. Avoid exercise if sick.",
    "233. Include stretching before bed.",
    "234. Avoid intense exercise at night.",
    "235. Track steps using pedometer or phone.",
    "236. Set daily movement goals.",
    "237. Join a fitness group or class.",
    "238. Stay consistent with workouts.",
    "239. Include fun physical activities.",
    "240. Avoid sitting while talking on phone.",
    "241. Drink water before feeling thirsty.",
    "242. Avoid sugary drinks frequently.",
    "243. Include electrolyte drinks if needed.",
    "244. Avoid overconsumption of sports drinks.",
    "245. Eat protein after workout.",
    "246. Include complex carbs before workout.",
    "247. Avoid heavy meals before exercise.",
    "248. Avoid late-night intense exercise.",
    "249. Protect skin from sun with SPF.",
    "250. Wear hats and sunglasses outdoors.",
    "251. Avoid direct sun during peak hours.",
    "252. Stay in shade when possible.",
    "253. Use sunscreen regularly.",
    "254. Avoid tanning beds.",
    "255. Maintain skin hydration.",
    "256. Use gentle cleansers for skin.",
    "257. Avoid harsh chemicals on skin.",
    "258. Check skin for moles regularly.",
    "259. Consult dermatologist for skin concerns.",
    "260. Avoid picking at skin.",
    "261. Keep nails clean and trimmed.",
    "262. Avoid nail-biting.",
    "263. Practice dental hygiene daily.",
    "264. Brush teeth twice a day.",
    "265. Floss teeth once a day.",
    "266. Visit dentist regularly.",
    "267. Avoid sugary snacks between meals.",
    "268. Limit acidic drinks like soda.",
    "269. Include calcium-rich foods for teeth.",
    "270. Drink plenty of water.",
    "271. Keep a healthy work-life balance.",
    "272. Avoid excessive overtime.",
    "273. Spend time with family and friends.",
    "274. Engage in hobbies regularly.",
    "275. Take mental health breaks.",
    "276. Practice meditation or mindfulness.",
    "277. Avoid excessive stress accumulation.",
    "278. Write a journal to release stress.",
    "279. Practice gratitude daily.",
    "280. Celebrate small wins every day.",
    "281. Avoid comparing yourself with others.",
    "282. Focus on personal growth.",
    "283. Set achievable goals.",
    "284. Take vacations to recharge.",
    "285. Practice deep relaxation techniques.",
    "286. Listen to music for relaxation.",
    "287. Engage in creative activities.",
    "288. Laugh often to reduce stress.",
    "289. Connect with supportive people.",
    "290. Seek professional help if needed.",
    "291. Practice self-compassion.",
    "292. Avoid negative self-talk.",
    "293. Maintain a positive mindset.",
    "294. Keep realistic expectations.",
    "295. Celebrate daily achievements.",
    "296. Avoid procrastination.",
    "297. Plan your day effectively.",
    "298. Use condom to have Sex.",
    "299. Eat Hygine Food.",
    "300. Always strive for balanced health."
    ]

    return render_template("healthtips.html", tips=tips)

# ---------------- YOGA ----------------
@app.route("/yoga")
def yoga():

    if "user" not in session:
        return redirect("/signin")

    yoga_poses = [

        {
            "name": "1.Mountain Pose (Tadasana)",
            "img": r"images\Yoga1.jpg",
            "info": "Improves posture, balance, and grounding."
        },
        {
            "name": "2.Chair Pose (Utkatasana)",
            "img": r"images\Yoga2.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "3.Warrior I (Virabhadrasana I)",
            "img": r"images\Yoga3.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "4. Warrior II (Virabhadrasana II)",
            "img": r"images\Yoga4.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "5. Warrior III (Virabhadrasana III)",
            "img": r"images\Yoga5.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "6. Reverse Warrior (Viparita Virabhadrasana)",
            "img": r"images\Yoga6.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "7. Extended Side Angle (Utthita Parsvakonasana)",
            "img": r"images\Yoga7.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "8. Triangle Pose (Trikonasana)",
            "img": r"images\Yoga8.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "9. Extended Triangle Pose (Utthita Trikonasana)",
            "img": r"images\Yoga9.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "10. Half Moon Pose (Ardha Chandrasana)",
            "img": r"images\Yoga10.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "11. Pyramid Pose (Parsvottanasana)",
            "img": r"images\Yoga11.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "12. Standing Forward Bend (Uttanasana)",
            "img": r"images\Yoga12.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "13. Standing Split (Urdhva Prasarita Eka Padasana)",
            "img": r"images\Yoga13.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "14. Wide-Legged Forward Bend (Prasarita Padottanasana)",
            "img": r"images\Yoga14.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "15. Garland Pose (Malasana)",
            "img": r"images\Yoga15.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "16. Eagle Pose (Garudasana)",
            "img": r"images\Yoga16.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "17. Dancer’s Pose (Natarajasana)",
            "img": r"images\Yoga17.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "18. Standing Hand to Big Toe Pose (Utthita Hasta Padangusthasana)",
            "img": r"images\Yoga18.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "19. Chair Twist (Parivrtta Utkatasana)",
            "img": r"images\Yoga19.jpg",
            "info": "Strengthens legs and spine, tones core."
        },
        {
            "name": "20. Easy Pose (Sukhasana)",
            "img": r"images\Yoga19.jpg",
            "info": "Strengthens legs and spine, tones core."
        },

    ]

    return render_template(
        "yoga.html",
        poses=yoga_poses
    )

# ---------------- MEDICINE ----------------
@app.route("/medicine", methods=["GET", "POST"])
def medicine():

    if "user" not in session:
        return redirect("/signin")

    suggestion = ""
    detected_symptoms = ""

    if request.method == "POST":

        problem = request.form["problem"].lower().strip()

        suggestion = "Consult doctor"

        # READ JSON FILE
        with open("medicine_database.json", "r") as file:

            database = json.load(file)

        # MATCH PROBLEM
        for item in database:

            if item["problem"].lower().strip() == problem:

                detected_symptoms = ", ".join(item["symptoms"])

                suggestion = ", ".join(item["suggestions"])

                # CURRENT DATE AND TIME
                current_date = datetime.now().strftime("%d-%m-%Y")

                current_time = datetime.now().strftime("%I:%M %p")

                # DATA TO SAVE
                data = {
                    "username": session["user"],
                    "date": current_date,
                    "time": current_time,
                    "problem": problem,
                    "symptoms": detected_symptoms,
                    "suggestion": suggestion
                }

                # OPEN OLD DATA
                if os.path.exists("medicine_data.json"):

                    with open("medicine_data.json", "r") as f:
                        all_data = json.load(f)

                else:
                    all_data = []

                # ADD NEW DATA
                all_data.append(data)

                # SAVE FILE
                with open("medicine_data.json", "w") as f:
                    json.dump(all_data, f, indent=4)

                break

    return render_template(
        "medicine.html",
        suggestion=suggestion,
        symptoms=detected_symptoms
    )

# ---------------- HISTORY ----------------
@app.route("/history")
def history():

    if "user" not in session:
        return redirect("/signin")

    username = session["user"]

    records = []

    if os.path.exists("medicine_data.json"):

        with open("medicine_data.json", "r") as f:
            all_data = json.load(f)

        for item in all_data:

            if item["user"] == username:
                records.append(item)

    return render_template(
        "history.html",
        records=records
    )

# -------------------------- Verify OTP -------------------
@app.route("/verify_captcha", methods=["GET", "POST"])
def verify_captcha():

    if request.method == "POST":

        entered_captcha = request.form["captcha"]

        if entered_captcha == session["captcha"]:

            users = load_users()

            temp = session["temp_user"]

            users[temp["username"]] = temp

            save_users(users)

            session["user"] = temp["username"]

            return redirect("/dashboard")

        else:
            return "Wrong CAPTCHA"

    return render_template(
        "verify_captcha.html",
        captcha=session["captcha"]
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)