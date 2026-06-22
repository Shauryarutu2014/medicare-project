import os
import json
import random
import csv
import io
from functools import wraps
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt as _bcrypt
import webauthn
from datetime import datetime, timezone




from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        AuthenticatorAttachment,
        PublicKeyCredentialDescriptor,
    )
    from webauthn.helpers.cose import COSEAlgorithmIdentifier
    from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
    WEBAUTHN_AVAILABLE = True
except Exception:
    WEBAUTHN_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "medicare-dev-secret-key-2024")

# ── Admin Panel SQLAlchemy DB (SQLite) ─────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://medicare_database_user:6ssEiOC01LoWdPrSnulD6Ko6vmHrWpaE@dpg-d8jq2kuk1jcs73e1rlk0-a.virginia-postgres.render.com/medicare_database"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
admin_db = SQLAlchemy(app)

# ── Admin Panel Models ─────────────────────────────────────────────────────────

class AdminAccount(admin_db.Model):
    __tablename__ = "admin_accounts"
    id = admin_db.Column(admin_db.Integer, primary_key=True)
    username = admin_db.Column(admin_db.String(80), unique=True, nullable=False)
    display_name = admin_db.Column(admin_db.String(120), nullable=False, default="")
    role = admin_db.Column(admin_db.String(20), nullable=False, default="admin")
    password_hash = admin_db.Column(admin_db.String(255), nullable=False)
    pin_hash = admin_db.Column(admin_db.String(255), nullable=True)
    webauthn_credential_id = admin_db.Column(admin_db.Text, nullable=True)
    webauthn_public_key = admin_db.Column(admin_db.Text, nullable=True)
    webauthn_sign_count = admin_db.Column(admin_db.Integer, default=0)
    created_at = admin_db.Column(admin_db.DateTime, default=datetime.utcnow)

    def check_password(self, password):
        return _bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def check_pin(self, pin):
        if not self.pin_hash:
            return False
        return _bcrypt.checkpw(pin.encode(), self.pin_hash.encode())

    def has_2fa(self):
        return bool(self.pin_hash or self.webauthn_credential_id)

    @property
    def is_superadmin(self):
        return self.role == "superadmin"


class AdminAppUser(admin_db.Model):
    __tablename__ = "admin_app_users"
    id = admin_db.Column(admin_db.Integer, primary_key=True)
    username = admin_db.Column(admin_db.String(80), unique=True, nullable=False)
    email = admin_db.Column(admin_db.String(120), unique=True, nullable=False)
    password_hash = admin_db.Column(admin_db.String(255), nullable=False)
    role = admin_db.Column(admin_db.String(20), default="user")
    status = admin_db.Column(admin_db.String(20), default="active")
    created_at = admin_db.Column(admin_db.DateTime, default=datetime.utcnow)
    searches = admin_db.relationship(
        "AdminSearchHistory", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def search_count(self):
        return len(self.searches)


class AdminSearchHistory(admin_db.Model):
    __tablename__ = "admin_search_history"
    id = admin_db.Column(admin_db.Integer, primary_key=True)
    user_id = admin_db.Column(admin_db.Integer, admin_db.ForeignKey("admin_app_users.id"), nullable=False)
    problem = admin_db.Column(admin_db.String(255), nullable=False)
    category = admin_db.Column(admin_db.String(80), default="general")
    results_count = admin_db.Column(admin_db.Integer, default=0)
    searched_at = admin_db.Column(admin_db.DateTime, default=datetime.utcnow)


ADMIN_PANEL_ACCOUNTS = [
    {
        "username": "shauryagadekar_admin2026",
        "display_name": "Shaurya Nitin Gadekar",
        "role": "admin",
        "password": "nsrshauryagadekar2014",
    },
    {
        "username": "harshthakre_admin2026",
        "display_name": "Harsh Sanjay Thakre",
        "role": "admin",
        "password": "smrharshthakre2013",
    },
    {
        "username": "gadekarshaurya2014",
        "display_name": "Shaurya Nitin Gadekar (Super Admin)",
        "role": "superadmin",
        "password": "shauryagadekar@27052014",
    },
    {
        "username": "thakreharsh2014",
        "display_name": "Harsh Sanjay Thakre  (Super Admin)",
        "role": "superadmin",
        "password": "harshthakre@09112013",
    }
]


def seed_admin_panel():
    for acc in ADMIN_PANEL_ACCOUNTS:
        existing = admin_db.session.query(AdminAccount).filter_by(username=acc["username"]).first()
        if existing:
            if not existing.display_name:
                existing.display_name = acc["display_name"]
        else:
            pw = _bcrypt.hashpw(acc["password"].encode(), _bcrypt.gensalt()).decode()
            admin_db.session.add(
                AdminAccount(
                    username=acc["username"],
                    display_name=acc["display_name"],
                    role=acc["role"],
                    password_hash=pw,
                )
            )
    if admin_db.session.query(AdminAppUser).count() == 0:
        import random as _random
        _random.seed(42)
        cats = ["health","education","medication","symptoms","treatment","diagnosis","nutrition","fitness","mental-health","general"]
        qs = ["diabetes symptoms","blood pressure medication","covid vaccine","headache relief","flu treatment","vitamin D benefits","anxiety management","cancer screening","diet plan","exercise routine","sleep disorders","allergy medicine","heart disease prevention","weight loss tips","prenatal care","physical therapy","online courses","math tutoring","science experiments","history lessons","language learning"]
        for i in range(1, 51):
            pw = _bcrypt.hashpw(f"user{i}pass".encode(), _bcrypt.gensalt()).decode()
            u = AdminAppUser(
                username=f"user{i:03d}",
                email=f"user{i}@example.com",
                password_hash=pw,
                role="admin" if i % 10 == 0 else "user",
                status="inactive" if i % 7 == 0 else "active",
                created_at=datetime.now(timezone.utc) - timedelta(days=_random.randint(1, 365)),
            )
            admin_db.session.add(u)
            admin_db.session.flush()
            for _ in range(_random.randint(0, 30)):
                admin_db.session.add(
                    AdminSearchHistory(
                        user_id=u.id,
                        problem=_random.choice(qs),
                        category=_random.choice(cats),
                        results_count=_random.randint(1, 50),
                        searched_at=datetime.now(timezone.utc) - timedelta(days=_random.randint(0, 60), hours=_random.randint(0, 23)),
                    )
                )
    admin_db.session.commit()


class AdminPaginator:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, (total + per_page - 1) // per_page)
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge or self.page - left_current - 1 < num < self.page + right_current or num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def admin_panel_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("signin"))
        if session.get("auth_stage") != "complete":
            return redirect(url_for("admin_verify_2fa"))
        return f(*args, **kwargs)
    return decorated


def admin_superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("signin"))
        if session.get("auth_stage") != "complete":
            return redirect(url_for("admin_verify_2fa"))
        if session.get("admin_role") != "superadmin":
            flash("Superadmin access required.", "error")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated


def get_admin_account():
    if "admin_id" not in session:
        return None
    return admin_db.session.get(AdminAccount, session["admin_id"])


def get_rp_id():
    return request.host.split(":")[0]


def get_origin():
    return request.host_url.rstrip("/")


# ── Initialize admin panel DB at startup ──────────────────────────────────────
with app.app_context():
    admin_db.create_all()
    seed_admin_panel()


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN USERNAMES & PASSWORDS — EDIT THIS SECTION TO CHANGE ADMIN CREDENTIALS
# Add or remove admins by editing the dictionary below.
# Format: "username": "password"
# ══════════════════════════════════════════════════════════════════════════════
ADMIN_USERS = {
    "shauryagadekar_admin2026": "scrypt:32768:8:1$LySTU8ASTVbrVPzb$7e87b299dc3424f9bab5d4873f7e0cb1f2e3506f79da4506662b509fc095072c98cc318c6e2fff630cebb47e370e6744104191792f3560f05cb485acb77e5e0f",   # Admin 1: Shaurya Nitin Gadekar
    "harshthakre_admin2026": "scrypt:32768:8:1$By2rvIE051bnaZIw$4ddddcaf3597bf8d2cfa866c8a215c45dd6c4a17de1783f713b27b939be43d62a0895564a7eec27415391f782de1e9dad841aab17eab8488ed35795f7412345e",      # Admin 2: Harsh Sanjay Thakre
}
# Admin display names (shown in the hidden admin panel)
ADMIN_DISPLAY = {
    "shauryagadekar_admin2026": "Shaurya Gadekar",
    "harshthakre_admin2026":    "Harsh Thakre",
}
# ══════════════════════════════════════════════════════════════════════════════
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://medicare_user:d7gaTAaBVVS4c5bGmwvCilMnACC9r6tz@dpg-d85efkgjs32c73aftmbg-a.virginia-postgres.render.com/medicare_f2fm"
)

def get_db():
    conn = psycopg2.connect(
        host="dpg-d8jq2kuk1jcs73e1rlk0-a.oregon-postgres.render.com",
        database="medicare_database",
        user="medicare_database_user",
        password="6ssEiOC01LoWdPrSnulD6Ko6vmHrWpaE",
        port="5432",
        sslmode="require"
    )
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                username VARCHAR(100),
                problem VARCHAR(255),
                suggestions TEXT,
                symptoms TEXT,
                searched_at TIMESTAMP DEFAULT NOW()
            )
        """)
    conn.commit()
    cur.close()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Protects hidden admin routes — redirects to signin if not admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return decorated


def load_medicines():
    data_path = os.path.join(os.path.dirname(__file__), "data", "medicines.json")
    with open(data_path, "r") as f:
        return json.load(f)


HEALTH_TIPS = [
    "Drink at least 8 glasses of water daily to stay hydrated.",
    "Eat a balanced diet rich in fruits, vegetables, and whole grains.",
    "Exercise for at least 30 minutes a day, 5 days a week.",
    "Get 7–9 hours of quality sleep every night.",
    "Avoid smoking and limit alcohol consumption.",
    "Wash your hands frequently to prevent infections.",
    "Schedule regular health check-ups with your doctor.",
    "Maintain a healthy body weight through diet and exercise.",
    "Reduce stress through meditation, yoga, or deep breathing.",
    "Limit processed foods, sugar, and saturated fats.",
    "Include omega-3 fatty acids in your diet (fish, walnuts, flaxseeds).",
    "Take vitamin D supplements if you have limited sun exposure.",
    "Practice good posture to avoid back and neck pain.",
    "Protect your skin from UV rays with sunscreen (SPF 30+).",
    "Eat breakfast every day to fuel your metabolism.",
    "Limit screen time and take breaks every hour.",
    "Keep a consistent daily routine for better mental health.",
    "Stay socially connected with friends and family.",
    "Learn to recognize signs of mental health issues and seek help.",
    "Avoid skipping meals — eat small portions throughout the day.",
    "Choose stairs over elevators whenever possible.",
    "Stretch for 5–10 minutes every morning.",
    "Eat more fiber to improve digestive health.",
    "Limit sodium intake to reduce blood pressure risk.",
    "Have your blood pressure checked regularly.",
    "Monitor your blood sugar if you have diabetes risk factors.",
    "Keep cholesterol levels in check with a heart-healthy diet.",
    "Use a helmet when riding a bicycle or motorcycle.",
    "Always wear a seatbelt when in a vehicle.",
    "Stay up to date with all recommended vaccinations.",
    "Avoid self-medicating — always consult a doctor.",
    "Learn basic first aid and CPR techniques.",
    "Keep a well-stocked first aid kit at home.",
    "Reduce caffeine intake if you have trouble sleeping.",
    "Practice mindfulness to reduce anxiety and stress.",
    "Limit sugary drinks and replace them with water or herbal tea.",
    "Read food labels to understand what you are consuming.",
    "Avoid eating late at night — stop eating 2–3 hours before bed.",
    "Keep your living environment clean and dust-free.",
    "Use air purifiers if you live in a high-pollution area.",
    "Get your eyes checked every 1–2 years.",
    "Visit the dentist every 6 months for cleaning and check-ups.",
    "Floss your teeth daily to prevent gum disease.",
    "Protect your hearing — avoid prolonged exposure to loud noise.",
    "Stay active during pregnancy with doctor-approved exercises.",
    "Breastfeed your baby if possible for at least 6 months.",
    "Track your menstrual cycle for early detection of irregularities.",
    "Perform monthly breast self-exams.",
    "Men over 50 should get a prostate screening.",
    "Women over 40 should get regular mammograms.",
    "Get a colorectal cancer screening starting at age 45.",
    "Avoid prolonged sitting — stand and walk every 30 minutes.",
    "Try intermittent fasting to improve metabolic health.",
    "Include probiotic-rich foods like yogurt and kefir in your diet.",
    "Eat slowly and chew thoroughly to improve digestion.",
    "Stay positive — a positive mindset boosts immunity.",
    "Laugh often — laughter is proven to reduce stress hormones.",
    "Spend time in nature to improve mental well-being.",
    "Garden or do outdoor activities to get fresh air and sunlight.",
    "Practice gratitude — write 3 things you are grateful for daily.",
    "Keep a health journal to track your diet, sleep, and exercise.",
    "Do strength training at least 2 days per week.",
    "Include cardio exercises like walking, running, or cycling.",
    "Try swimming — it is excellent for full-body fitness.",
    "Yoga improves flexibility, balance, and mental clarity.",
    "Pilates strengthens your core and improves posture.",
    "Dancing is a fun and effective cardio workout.",
    "Avoid sitting with crossed legs for long periods.",
    "Elevate your legs when resting to improve blood circulation.",
    "Cold showers can boost immunity and improve alertness.",
    "Steam inhalation helps with respiratory issues.",
    "Ginger tea is effective for nausea and inflammation.",
    "Turmeric has powerful anti-inflammatory properties.",
    "Honey is a natural antibiotic and soothes sore throats.",
    "Apple cider vinegar can help with digestion and blood sugar.",
    "Garlic is a natural immune booster.",
    "Lemon water in the morning supports detoxification.",
    "Green tea is rich in antioxidants and supports heart health.",
    "Chamomile tea promotes relaxation and better sleep.",
    "Peppermint tea relieves headaches and digestive issues.",
    "Eat more leafy greens like spinach, kale, and broccoli.",
    "Include colorful vegetables — the more color, the more nutrients.",
    "Nuts and seeds are excellent sources of healthy fats.",
    "Avocados provide heart-healthy monounsaturated fats.",
    "Berries are among the highest-antioxidant foods available.",
    "Legumes like beans and lentils are high in protein and fiber.",
    "Whole grain bread is healthier than white refined bread.",
    "Sweet potatoes are rich in beta-carotene and fiber.",
    "Eggs are a complete protein source with essential nutrients.",
    "Salmon is one of the best sources of omega-3 fatty acids.",
    "Drink warm milk before bed to promote better sleep.",
    "Keep your bedroom cool and dark for better sleep quality.",
    "Avoid checking your phone first thing in the morning.",
    "Spend the first 30 minutes of your day without screens.",
    "Set boundaries around work to maintain work-life balance.",
    "Take mental health days when needed — rest is productive.",
    "Talk to a therapist or counselor when feeling overwhelmed.",
    "Practice deep diaphragmatic breathing for 5 minutes daily.",
    "Cold therapy (ice baths) reduces muscle soreness after workouts.",
    "Massage therapy can reduce muscle tension and stress.",
    "Acupuncture may help with chronic pain and stress.",
    "Tai Chi is gentle and effective for balance and flexibility.",
    "Foam rolling helps release tight muscles.",
    "Wear supportive footwear to prevent foot and back problems.",
    "Stretch your hip flexors if you sit all day.",
    "Do neck stretches to prevent computer-related neck pain.",
    "Rest your eyes with the 20-20-20 rule: every 20 minutes, look 20 feet away for 20 seconds.",
    "Blue light glasses can reduce eye strain from screens.",
    "Maintain proper hydration during exercise.",
    "Replace electrolytes after intense sweating.",
    "Eat protein within 30 minutes after a workout.",
    "Warm up before exercise to prevent injury.",
    "Cool down and stretch after every workout.",
    "Do not exercise on an empty stomach — eat a light snack.",
    "Listen to your body and rest when you feel pain.",
    "Overtraining can be harmful — rest days are essential.",
    "Track your steps — aim for 10,000 steps per day.",
    "Stand desks can help reduce the impact of prolonged sitting.",
    "Keep your workspace ergonomically organized.",
    "Wear a back brace if you have chronic lower back pain.",
    "Orthotics can correct gait issues and prevent joint pain.",
    "Do pelvic floor exercises to prevent incontinence.",
    "Kegel exercises are beneficial for both men and women.",
    "Avoid drinking too much liquid before bed to prevent nighttime waking.",
    "Practice progressive muscle relaxation for better sleep.",
    "Visualize calming scenes when you cannot fall asleep.",
    "Journaling before bed helps clear your mind.",
    "Consistent wake times are more important than consistent bedtimes.",
    "Nap for no more than 20–30 minutes to avoid grogginess.",
    "Spend time with pets — they reduce stress and loneliness.",
    "Volunteering and helping others improves mental health.",
    "Learn a new skill — mental stimulation protects brain health.",
    "Read for at least 20 minutes daily.",
    "Play brain games like puzzles and chess to stay mentally sharp.",
    "Travel and new experiences create lasting happiness.",
    "Music therapy can reduce anxiety and improve mood.",
    "Art therapy is effective for trauma and emotional healing.",
    "Writing therapy helps process difficult emotions.",
    "Support groups can be invaluable for chronic illness management.",
    "Track your moods using an app or journal.",
    "Recognize burnout early: fatigue, cynicism, reduced effectiveness.",
    "Set realistic goals to avoid feeling overwhelmed.",
    "Practice saying no — boundaries protect your energy.",
    "Spend time alone to recharge if you are introverted.",
    "Extroverts should seek social activities for energy.",
    "Forgiveness reduces stress and improves heart health.",
    "Compassion toward yourself and others reduces cortisol.",
    "Altruism and giving increase happiness hormones.",
    "Connect with your sense of purpose and meaning in life.",
    "Regular spiritual or religious practice improves mental health.",
    "Nature walks lower cortisol and blood pressure.",
    "Gardening reduces depression and anxiety.",
    "Pet therapy is used clinically for depression and PTSD.",
    "Volunteering extends lifespan and reduces depression.",
    "Strong social ties are the #1 predictor of longevity.",
    "Marriage and committed relationships correlate with better health.",
    "Loneliness has the same health impact as smoking 15 cigarettes a day.",
    "Keep in touch with old friends — social capital is health capital.",
    "Cook at home more often — restaurant food is higher in calories and sodium.",
    "Meal prep on weekends to make healthy eating easier during the week.",
    "Avoid eating while distracted — mindful eating reduces overeating.",
    "Use smaller plates to naturally control portion sizes.",
    "Eat the rainbow — each color represents different phytonutrients.",
    "Avoid crash diets — they slow metabolism and cause muscle loss.",
    "Intermittent fasting (16:8) is effective for weight management.",
    "Stay consistent — health is built through daily habits, not perfection.",
    "Small changes add up — you do not need a dramatic overhaul.",
    "Celebrate non-scale victories: energy, mood, and strength.",
    "Progress over perfection is the key to long-term health.",
    "Make health fun — find activities you genuinely enjoy.",
    "Health is wealth — invest in it daily.",
    "Prevention is always better than cure.",
    "Your body is your most important asset — treat it accordingly.",
    "Aging gracefully is possible with consistent healthy habits.",
    "It is never too late to start living a healthier life.",
    "Even 5 minutes of exercise is better than none.",
    "Start small and build gradually — consistency beats intensity.",
    "Find an accountability partner for fitness goals.",
    "Join a class or club to make exercise social.",
    "Set specific, measurable, achievable health goals.",
    "Review your health goals monthly and adjust as needed.",
    "Reward yourself (non-food rewards) when you reach milestones.",
    "Document your health journey with photos and notes.",
    "Use a fitness tracker to stay motivated.",
    "Apps like MyFitnessPal can help track nutrition.",
    "Headspace or Calm apps can guide meditation practice.",
    "Sleep tracking apps can identify poor sleep patterns.",
    "Regular health apps help manage chronic conditions.",
    "Telemedicine makes access to doctors easier than ever.",
    "Do not delay seeking medical care — early detection saves lives.",
    "Know your family health history — it affects your risk factors.",
    "Get genetic testing if you have a strong family history of disease.",
    "Ask your doctor about age-appropriate cancer screenings.",
    "Know the warning signs of a heart attack and stroke.",
    "FAST: Face drooping, Arm weakness, Speech difficulty, Time to call 911.",
    "Signs of a heart attack: chest pain, shortness of breath, left arm pain.",
    "Carry nitroglycerin if prescribed for heart conditions.",
    "Always carry a list of your medications.",
    "Wear a medical ID bracelet if you have serious conditions.",
    "Learn the Heimlich maneuver — it can save a life.",
    "Know your blood type in case of emergency.",
    "Keep an emergency contact list accessible on your phone.",
    "Inform loved ones about your medical conditions.",
    "Have a healthcare proxy or advance directive in place.",
    "Mental health is just as important as physical health.",
    "Seek help without shame — there is no weakness in asking for support.",
    "Depression and anxiety are medical conditions, not character flaws.",
    "ADHD, autism, and other neurodivergences deserve understanding.",
    "Check in on your friends — mental health crises often go unnoticed.",
    "Suicide hotlines are available 24/7 — you are not alone.",
    "Recovery is possible — do not give up on yourself or others.",
    "Self-care is not selfish — it enables you to care for others.",
    "Prioritize your health — everything else depends on it.",
    "Drink herbal tea instead of sugary beverages.",
    "Fermented foods improve gut microbiome health.",
    "Prebiotic foods (onions, garlic, bananas) feed good bacteria.",
    "A healthy gut supports immunity and mental health.",
    "The gut-brain axis connects your digestive and nervous systems.",
    "Chronic inflammation is linked to most modern diseases.",
    "Anti-inflammatory foods include berries, fatty fish, and olive oil.",
    "Reduce inflammatory foods: processed meats, refined carbs, sugar.",
    "Fasting can trigger cellular autophagy (cellular cleanup).",
    "Cold exposure activates brown fat and boosts metabolism.",
    "Sauna use is linked to lower cardiovascular disease risk.",
    "Breathwork techniques like Wim Hof improve stress response.",
    "Time in nature (green spaces) measurably improves mood.",
    "Forest bathing (Shinrin-yoku) lowers cortisol and blood pressure.",
    "Adequate magnesium supports sleep, mood, and muscle function.",
    "Most people are deficient in vitamin D, magnesium, and zinc.",
    "B12 deficiency is common in vegetarians and vegans — supplement it.",
    "Iron deficiency is the most common nutritional deficiency worldwide.",
    "Calcium and vitamin D together support bone density.",
    "Potassium-rich foods (bananas, potatoes) support heart and muscle health.",
    "Antioxidants protect your cells from oxidative stress.",
    "Polyphenols in dark chocolate have cardioprotective effects.",
    "Curcumin in turmeric is one of the most powerful natural anti-inflammatories.",
    "Quercetin in apples and onions reduces allergy symptoms.",
    "Lycopene in tomatoes is linked to reduced prostate cancer risk.",
    "Sulforaphane in broccoli is a powerful cancer-fighting compound.",
    "Collagen supports skin elasticity and joint health.",
    "Hyaluronic acid supports joint lubrication and skin moisture.",
    "CoQ10 supports mitochondrial energy production and heart health.",
    "Alpha-lipoic acid is a potent antioxidant that supports nerve health.",
    "Ashwagandha is an adaptogen that reduces cortisol and stress.",
    "Rhodiola helps with mental fatigue and resilience under stress.",
    "Lion's mane mushroom supports cognitive function and nerve growth.",
    "Melatonin supplementation helps reset circadian rhythm.",
    "L-theanine (in tea) promotes calm focus without drowsiness.",
    "5-HTP supports serotonin production and mood stability.",
    "Milk thistle supports liver detoxification.",
    "Elderberry is a powerful antiviral and immune booster.",
    "Zinc lozenges can reduce cold duration if taken at onset.",
    "Vitamin C in high doses can reduce the severity of infections.",
    "Probiotics reduce antibiotic-associated diarrhea.",
    "Digestive enzymes improve nutrient absorption after meals.",
    "Apple cider vinegar before meals may improve digestion.",
    "Psyllium husk is an excellent soluble fiber for gut health.",
    "Aloe vera juice supports gut health and acid reflux.",
    "Berberine has powerful blood sugar and cholesterol-lowering effects.",
    "Cinnamon improves insulin sensitivity.",
    "Chromium picolinate supports blood sugar regulation.",
    "Bitter melon is used traditionally to manage blood sugar.",
    "Fenugreek seeds slow sugar absorption in digestion.",
    "Hawthorn berry supports cardiovascular health.",
    "Aged garlic extract significantly reduces blood pressure.",
    "Hibiscus tea lowers blood pressure naturally.",
    "Regular sauna use mimics cardio benefits.",
    "Zone 2 cardio training is optimal for mitochondrial health.",
    "VO2 max is the best predictor of long-term health and longevity.",
    "Grip strength is a surprising predictor of overall health.",
    "Balance training reduces fall risk in older adults.",
    "Flexibility training prevents injury and improves mobility.",
    "Compound movements (squats, deadlifts) maximize hormonal response.",
    "Heavy resistance training protects bone density as we age.",
    "Muscle mass is strongly correlated with longevity.",
    "Protein intake should be 1.6–2.2g per kg body weight for active people.",
    "Creatine monohydrate is the most researched and effective supplement.",
    "Caffeine is effective for improving athletic performance.",
    "Beetroot juice improves endurance through nitrate conversion.",
    "Tart cherry juice reduces exercise-induced muscle soreness.",
    "Adequate sleep is the most powerful recovery tool available.",
    "Growth hormone is primarily released during deep sleep.",
    "Sleep deprivation increases cortisol and decreases testosterone.",
    "Alcohol disrupts REM sleep and impairs recovery.",
    "Smoking significantly increases the risk of lung cancer and heart disease.",
    "Secondhand smoke is harmful to children and non-smokers.",
    "Sugary drinks increase diabetes risk independent of weight.",
    "Processed meats are classified as Group 1 carcinogens by WHO.",
    "Air fresheners and candles release volatile organic compounds (VOCs).",
    "BPA and phthalates in plastics are endocrine disruptors — use glass or stainless.",
    "Fluoride in toothpaste prevents cavities — but do not swallow it.",
    "Oil pulling (swishing coconut oil) may reduce oral bacteria.",
    "Water flossers are more effective than string floss for some people.",
    "Brush your teeth for 2 minutes, twice a day.",
    "Replace your toothbrush every 3 months.",
    "Regular flossing reduces the risk of heart disease.",
    "Gum disease bacteria can travel to the heart and brain.",
    "The health of your mouth reflects the health of your entire body.",
]

YOGA_POSES = [
    {"name": "Mountain Pose (Tadasana)", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80", "benefits": "Improves posture, strengthens thighs and ankles, increases body awareness and steadiness.", "difficulty": "Beginner", "duration": "30–60 seconds"},
    {"name": "Downward Dog (Adho Mukha Svanasana)", "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400&q=80", "benefits": "Stretches hamstrings, calves, and spine. Builds arm and shoulder strength. Energizes the body.", "difficulty": "Beginner", "duration": "1–3 minutes"},
    {"name": "Warrior I (Virabhadrasana I)", "image": "https://images.unsplash.com/photo-1599901860904-17e6ed7083a0?w=400&q=80", "benefits": "Builds strength in legs and core, improves balance, opens hips and chest.", "difficulty": "Beginner", "duration": "30–60 seconds each side"},
    {"name": "Warrior II (Virabhadrasana II)", "image": "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=400&q=80", "benefits": "Strengthens legs and arms, improves focus and stamina, stretches hips and groin.", "difficulty": "Beginner", "duration": "30–60 seconds each side"},
    {"name": "Tree Pose (Vrksasana)", "image": "https://images.unsplash.com/photo-1510894347713-fc3ed6fdf539?w=400&q=80", "benefits": "Improves balance and concentration, strengthens legs, opens hips.", "difficulty": "Beginner", "duration": "30–60 seconds each side"},
    {"name": "Child's Pose (Balasana)", "image": "https://images.unsplash.com/photo-1552196563-55cd4e45efb3?w=400&q=80", "benefits": "Gently stretches hips, thighs, and ankles. Relieves stress and calms the mind.", "difficulty": "Beginner", "duration": "1–3 minutes"},
    {"name": "Cobra Pose (Bhujangasana)", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80", "benefits": "Strengthens spine, opens chest, stimulates abdominal organs, relieves back pain.", "difficulty": "Beginner", "duration": "15–30 seconds"},
    {"name": "Bridge Pose (Setu Bandha Sarvangasana)", "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400&q=80", "benefits": "Strengthens glutes, hamstrings, and back. Opens chest. Calms the nervous system.", "difficulty": "Beginner", "duration": "30–60 seconds"},
    {"name": "Seated Forward Bend (Paschimottanasana)", "image": "https://images.unsplash.com/photo-1599901860904-17e6ed7083a0?w=400&q=80", "benefits": "Stretches hamstrings and spine, calms the brain, relieves stress and mild depression.", "difficulty": "Intermediate", "duration": "1–3 minutes"},
    {"name": "Pigeon Pose (Eka Pada Rajakapotasana)", "image": "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=400&q=80", "benefits": "Opens hips deeply, stretches hip flexors and rotators, relieves lower back pain.", "difficulty": "Intermediate", "duration": "1–3 minutes each side"},
    {"name": "Triangle Pose (Trikonasana)", "image": "https://images.unsplash.com/photo-1510894347713-fc3ed6fdf539?w=400&q=80", "benefits": "Stretches legs, hips, and spine. Strengthens core. Improves digestion and balance.", "difficulty": "Beginner", "duration": "30–60 seconds each side"},
    {"name": "Plank Pose (Phalakasana)", "image": "https://images.unsplash.com/photo-1552196563-55cd4e45efb3?w=400&q=80", "benefits": "Builds core, arm, and shoulder strength. Tones the abdomen. Improves posture.", "difficulty": "Beginner", "duration": "30–60 seconds"},
    {"name": "Camel Pose (Ustrasana)", "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400&q=80", "benefits": "Opens chest and throat, stretches front body, stimulates kidneys and adrenal glands.", "difficulty": "Intermediate", "duration": "20–30 seconds"},
    {"name": "Boat Pose (Navasana)", "image": "https://images.unsplash.com/photo-1599901860904-17e6ed7083a0?w=400&q=80", "benefits": "Strengthens core and hip flexors, tones abdominal muscles, improves balance.", "difficulty": "Intermediate", "duration": "30–60 seconds"},
    {"name": "Headstand (Sirsasana)", "image": "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=400&q=80", "benefits": "Increases blood flow to brain, builds shoulder and arm strength, calms the nervous system.", "difficulty": "Advanced", "duration": "30 seconds to 3 minutes"},
    {"name": "Shoulder Stand (Sarvangasana)", "image": "https://images.unsplash.com/photo-1510894347713-fc3ed6fdf539?w=400&q=80", "benefits": "Stimulates thyroid gland, improves blood circulation, calms the nervous system.", "difficulty": "Advanced", "duration": "1–5 minutes"},
    {"name": "Lotus Pose (Padmasana)", "image": "https://images.unsplash.com/photo-1552196563-55cd4e45efb3?w=400&q=80", "benefits": "Opens hips and knees, improves posture for meditation, calms the mind.", "difficulty": "Advanced", "duration": "5–30 minutes"},
    {"name": "Corpse Pose (Savasana)", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80", "benefits": "Promotes deep relaxation, reduces stress and fatigue, integrates benefits of practice.", "difficulty": "Beginner", "duration": "5–15 minutes"},
    {"name": "Extended Side Angle (Utthita Parsvakonasana)", "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=400&q=80", "benefits": "Strengthens legs, stretches sides, improves endurance and stability.", "difficulty": "Beginner", "duration": "30–60 seconds each side"},
    {"name": "Happy Baby (Ananda Balasana)", "image": "https://images.unsplash.com/photo-1599901860904-17e6ed7083a0?w=400&q=80", "benefits": "Releases lower back, stretches inner groin, calms the nervous system.", "difficulty": "Beginner", "duration": "1–2 minutes"},
    {"name": "Crow Pose (Bakasana)", "image": "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=400&q=80", "benefits": "Builds arm and wrist strength, tones core, improves balance and concentration.", "difficulty": "Advanced", "duration": "10–30 seconds"},
    {"name": "Half Moon Pose (Ardha Chandrasana)", "image": "https://images.unsplash.com/photo-1510894347713-fc3ed6fdf539?w=400&q=80", "benefits": "Strengthens legs and core, improves balance, stretches hamstrings and spine.", "difficulty": "Intermediate", "duration": "30–60 seconds each side"},
    {"name": "Supine Twist (Supta Matsyendrasana)", "image": "https://images.unsplash.com/photo-1552196563-55cd4e45efb3?w=400&q=80", "benefits": "Releases spine, massages abdominal organs, reduces stress and tension.", "difficulty": "Beginner", "duration": "1–2 minutes each side"},
    {"name": "Half Pigeon (Ardha Kapotasana)", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80", "benefits": "Releases hip tension, stretches piriformis, reduces sciatic nerve pain.", "difficulty": "Intermediate", "duration": "1–2 minutes each side"},
]


# ─── Public Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        captcha_answer = request.form.get("captcha_answer", "").strip()
        captcha_expected = session.get("captcha_answer")

        # ---------------- VALIDATION ----------------
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("signup"))

        if not captcha_expected or captcha_answer != str(captcha_expected):
            flash("Incorrect CAPTCHA answer. Please try again.", "danger")
            return redirect(url_for("signup"))

        # ---------------- HASH PASSWORD ----------------
        password_hash = generate_password_hash(password)

        # ---------------- DATABASE INSERT ----------------
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password_hash)
            )
            conn.commit()

            flash("Account created successfully! Please sign in.", "success")
            return redirect(url_for("signin"))

        except Exception as e:
            conn.rollback()
            print("❌ SIGNUP ERROR:", repr(e))   # IMPORTANT DEBUG LINE

            flash("Username or email already exists or database error.", "danger")
            return redirect(url_for("signup"))

        finally:
            cur.close()
            conn.close()

    # ---------------- GET REQUEST (CAPTCHA) ----------------
    a, b = random.randint(1, 9), random.randint(1, 9)
    session["captcha_answer"] = a + b
    session["captcha_question"] = f"{a} + {b}"

    return render_template("signup.html", captcha=session["captcha_question"])

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        captcha_answer = request.form.get("captcha_answer", "").strip()
        captcha_expected = session.get("captcha_answer")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("signin"))
        if captcha_answer != str(captcha_expected):
            flash("Incorrect CAPTCHA answer.", "danger")
            return redirect(url_for("signin"))

        # ── Check if admin username exists → redirect to admin login page ────
        admin_check = admin_db.session.query(AdminAccount).filter_by(username=username).first()
        if admin_check:
            session["admin_prefill"] = username
            return redirect(url_for("admin_login"))
        # ───────────────────────────────────────────────────────────────────

        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
        except Exception:
            flash("Database error. Please try again.", "danger")
            return redirect(url_for("signin"))

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("signin"))

    a, b = random.randint(1, 9), random.randint(1, 9)
    session["captcha_answer"] = a + b
    session["captcha_question"] = f"{a} + {b}"
    return render_template("signin.html", captcha=session["captcha_question"])


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ─── User Routes ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # COUNT SEARCHES
        cur.execute("""
            SELECT COUNT(*) 
            FROM history 
            WHERE username = %s
        """, (session["username"],))

        history_count = cur.fetchone()[0]

        # RECENT SEARCHES
        cur.execute("""
            SELECT * 
            FROM history 
            WHERE username = %s 
            ORDER BY searched_at DESC 
            LIMIT 3
        """, (session["username"],))

        recent = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        print("DASHBOARD ERROR:", e)
        history_count = 0
        recent = []

    # ✅ IMPORTANT: THIS MUST ALWAYS RUN
    return render_template(
        "dashboard.html",
        username=session["username"],
        history_count=history_count,
        recent=recent,
        tips_count=len(HEALTH_TIPS),
        yoga_count=len(YOGA_POSES)
    )

@app.route("/health-tips")
@login_required
def health_tips():
    return render_template("health_tips.html", tips=HEALTH_TIPS, total=len(HEALTH_TIPS))


@app.route("/yoga")
@login_required
def yoga():
    return render_template("yoga.html", poses=YOGA_POSES)


@app.route("/medicine", methods=["GET", "POST"])
@login_required
def medicine():
    medicines = [
    {
        "problem": "Stress / Anxiety",
        "symptoms": ["Restlessness", "Fast heartbeat", "Poor sleep"],
        "suggestions": ["Breathing exercises", "Meditation", "Talk to someone"]
    },
        {"problem": "Cold / Flu",
         "symptoms": ["Runny nose", "Cough", "Fever"],
         "suggestions": ["Rest", "Warm fluids", "Steam inhalation"]
         },
        {
            "problem": "Headache",
            "symptoms": ["Head pain", "Sensitivity to light", "Tiredness"],
            "suggestions": ["Rest in dark room", "Hydration", "Pain relief medicine"]
        },
        {
            "problem": "Stomach Issues",
            "symptoms": ["Stomach pain", "Bloating", "Nausea"],
            "suggestions": ["Light diet", "ORS", "Avoid spicy food"]
        },
        {
            "problem": "Fatigue",
            "symptoms": ["Tiredness", "Low energy", "Sleepiness"],
            "suggestions": ["Proper sleep", "Balanced diet", "Hydration"]
        },
        {
            "problem": "Allergy",
            "symptoms": ["Sneezing", "Itchy eyes", "Skin rash"],
            "suggestions": ["Avoid allergens", "Antihistamines", "Clean environment"]
        },
        {
            "problem": "Diabetes Symptoms",
            "symptoms": ["Frequent urination", "Thirst", "Fatigue"],
            "suggestions": ["Healthy diet", "Exercise", "Sugar control"]
        },
        {
            "problem": "Blood Pressure",
            "symptoms": ["Dizziness", "Headache", "Chest discomfort"],
            "suggestions": ["Reduce salt", "Exercise", "Medication"]
        },
        {
            "problem": "Migraine",
            "symptoms": ["Severe headache", "Nausea", "Light sensitivity"],
            "suggestions": ["Rest", "Cold compress", "Medication"]
        },
        {
            "problem": "Skin Infection",
            "symptoms": ["Redness", "Itching", "Swelling"],
            "suggestions": ["Clean area", "Antiseptic cream", "Doctor consultation"]
        },
        {
            "problem": "gout",
            "symptoms": ["Intense joint pain (often big toe)", "Lingering discomfort", "Inflammation and redness",
                         "Limited range of motion"],
            "suggestions": ["Colchicine (0.6mg)", "Allopurinol (100mg)", "Indomethacin (50mg)", "Naproxen (500mg)"]
        },
        {
            "problem": "vertigo",
            "symptoms": ["Spinning sensation", "Dizziness", "Balance problems", "Nausea", "Vomiting",
                         "Lightheadedness"],
            "suggestions": ["Meclizine (25mg)", "Betahistine (8-16mg)", "Dimenhydrinate (50mg)"]
        },
        {
            "problem": "hemorrhoids",
            "symptoms": ["Rectal bleeding", "Itching or irritation", "Pain or discomfort", "Swelling around the anus"],
            "suggestions": ["Hydrocortisone suppository", "Witch hazel pads", "Lidocaine cream",
                            "Stool softeners (Docusate sodium)"]
        },
        {
            "problem": "sinusitis",
            "symptoms": ["Facial pressure and pain", "Congestion", "Thick nasal discharge", "Reduced sense of smell",
                         "Ear pressure"],
            "suggestions": ["Fluticasone nasal spray", "Pseudoephedrine (60mg)", "Saline nasal irrigation",
                            "Guaifenesin"]
        },
        {
            "problem": "anemia",
            "symptoms": ["Fatigue", "Weakness", "Pale skin", "Chest pain", "Cold hands and feet",
                         "Shortness of breath"],
            "suggestions": ["Ferrous Sulfate (325mg)", "Ferrous Gluconate", "Vitamin B12 supplements", "Folic Acid"]
        },
        {
            "problem": "tinnitus",
            "symptoms": ["Ringing in ears", "Buzzing, hissing, or roaring sound", "Hearing loss (sometimes)"],
            "suggestions": ["Ginkgo Biloba (natural)", "Magnesium supplements", "Zinc supplements"]
        },
        {
            "problem": "sciatica",
            "symptoms": ["Pain radiating from lower back to leg", "Numbness or tingling in foot", "Muscle weakness"],
            "suggestions": ["Ibuprofen (400mg)", "Gabapentin (300mg - prescription)", "Diclofenac topical"]
        },
        {
            "problem": "heartburn",
            "symptoms": ["Burning chest pain", "Sour taste in mouth", "Difficulty swallowing", "Regurgitation"],
            "suggestions": ["Famotidine (20mg)", "Magnesium Hydroxide", "Calcium Carbonate", "Esomeprazole"]
        },
        {
            "problem": "conjunctivitis",
            "symptoms": ["Redness in white of eye", "Increased tears", "Thick yellow discharge",
                         "Gritty feeling in eyes"],
            "suggestions": ["Antibiotic eye drops (as prescribed)", "Lubricating eye drops", "Antihistamine drops"]
        },
        {
            "problem": "canker sores",
            "symptoms": ["Small painful ulcers inside mouth", "Red border around white/yellow center",
                         "Tingling sensation before sore appears"],
            "suggestions": ["Benzocaine oral gel", "Hydrogen peroxide rinse", "Saltwater gargle",
                            "Triamcinolone dental paste"]
        },
        {
            "problem": "heat exhaustion",
            "symptoms": ["Heavy sweating", "Rapid pulse", "Muscle cramps", "Headache", "Nausea", "Dizziness"],
            "suggestions": ["Electrolyte replenishment fluids", "Cool water"]
        },
        {
            "problem": "ingrown toenail",
            "symptoms": ["Pain and tenderness at nail edge", "Swelling", "Redness", "Possible infection/pus"],
            "suggestions": ["Topical antibiotic ointment", "Pain relief (Ibuprofen)"]
        },
        {
            "problem": "tinea pedis (athlete's foot)",
            "symptoms": ["Itchy, scaly rash between toes", "Cracked skin", "Blisters", "Burning sensation"],
            "suggestions": ["Terbinafine cream", "Clotrimazole cream", "Miconazole powder"]
        },
        {
            "problem": "dysmenorrhea (menstrual cramps)",
            "symptoms": ["Throbbing/cramping pain in lower abdomen", "Lower back pain", "Radiating pain to thighs",
                         "Nausea"],
            "suggestions": ["Ibuprofen (400mg)", "Naproxen (250mg)", "Heat patch"]
        },
        {
            "problem": "frostbite",
            "symptoms": ["Cold, prickling feeling", "Numbness", "Red, white, or gray skin", "Hard or waxy skin"],
            "suggestions": ["Pain relief (Ibuprofen)"]
        },
        {
            "problem": "laryngitis",
            "symptoms": ["Hoarseness", "Weak voice", "Tickling throat", "Dry throat", "Sore throat"],
            "suggestions": ["Throat lozenges", "Acetaminophen"]
        },
        {
            "problem": "scabies",
            "symptoms": ["Intense itching (worse at night)", "Thin burrow tracks on skin", "Small blisters or bumps",
                         "Rash"],
            "suggestions": ["Permethrin cream (5%)", "Crotamiton cream", "Antihistamines (for itching)"]
        },
        {
            "problem": "otitis media (ear infection)",
            "symptoms": ["Ear pain", "Difficulty hearing", "Fluid drainage from ear", "Fever",
                         "Irritability in children"],
            "suggestions": ["Amoxicillin (if bacterial)", "Acetaminophen (for pain)", "Decongestants"]
        },
        {
            "problem": "hemiplegia",
            "symptoms": ["Paralysis on one side of the body", "Muscle stiffness", "Difficulty walking",
                         "Loss of fine motor skills"],
            "suggestions": ["Physical therapy", "Occupational therapy", "Muscle relaxants (Baclofen)"]
        },
        {
            "problem": "epistaxis (nosebleed)",
            "symptoms": ["Bleeding from one or both nostrils", "Blood in the back of the throat"],
            "suggestions": ["Topical decongestant spray (short term)", "Saline nasal spray"]
        },
        {
            "problem": "celiac disease",
            "symptoms": ["Chronic diarrhea", "Abdominal pain", "Bloating", "Fatigue", "Weight loss", "Anemia"],
            "suggestions": ["Strict gluten-free diet", "Vitamin/Mineral supplements"]
        },
        {
            "problem": "plantar fasciitis",
            "symptoms": ["Stabbing heel pain (usually first steps in morning)", "Stiffness in the arch of the foot"],
            "suggestions": ["Ibuprofen", "Orthotic shoe inserts", "Night splints"]
        },
        {
            "problem": "hypoglycemia",
            "symptoms": ["Shakiness", "Sweating", "Hunger", "Confusion", "Fast heartbeat", "Dizziness"],
            "suggestions": ["Glucose tablets", "Fruit juice or regular soda (fast-acting sugar)"]
        },
        {
            "problem": "tendonitis",
            "symptoms": ["Dull ache in the area of a tendon", "Mild swelling", "Tenderness", "Pain with movement"],
            "suggestions": ["Naproxen", "Diclofenac topical gel"]
        },
        {
            "problem": "bronchitis",
            "symptoms": ["Persistent cough (mucus-producing)", "Shortness of breath", "Chest soreness",
                         "Low-grade fever", "Chills"],
            "suggestions": ["Guaifenesin (expectorant)", "Dextromethorphan (cough suppressant)", "Hydration"]
        },
        {
            "problem": "osteoporosis",
            "symptoms": ["Back pain", "Loss of height over time", "Stooped posture",
                         "Bone fractures occurring more easily than expected"],
            "suggestions": ["Calcium supplements", "Vitamin D3", "Bisphosphonates (e.g., Alendronate)"]
        },
        {
            "problem": "urinary incontinence",
            "symptoms": ["Leaking urine during physical activity (stress)", "Sudden, strong urge to urinate",
                         "Frequent nocturnal urination"],
            "suggestions": ["Oxybutynin (anticholinergic)", "Mirabegron"]
        },
        {
            "problem": "gastritis",
            "symptoms": ["Gnawing or burning ache in upper abdomen", "Nausea", "Vomiting", "Feeling of fullness"],
            "suggestions": ["Antacids", "H2 blockers (Famotidine)", "Proton pump inhibitors (Omeprazole)"]
        },
        {
            "problem": "shingles",
            "symptoms": ["Painful burning or tingling skin", "Red rash appearing a few days later",
                         "Fluid-filled blisters", "Fever", "Headache"],
            "suggestions": ["Acyclovir (antiviral)", "Valacyclovir", "Calamine lotion", "Lidocaine patches"]
        },
        {
            "problem": "hypothyroidism",
            "symptoms": ["Fatigue", "Increased sensitivity to cold", "Weight gain", "Dry skin", "Thinning hair",
                         "Muscle weakness"],
            "suggestions": ["Levothyroxine (synthetic hormone)"]
        },
        {
            "problem": "angina",
            "symptoms": ["Chest pain/pressure", "Discomfort spreading to arms, neck, or jaw", "Shortness of breath",
                         "Sweating"],
            "suggestions": ["Nitroglycerin (sublingual tablets or spray)", "Aspirin"]
        },
        {
            "problem": "psoriasis",
            "symptoms": ["Red patches of skin covered with thick, silvery scales", "Small scaling spots",
                         "Dry, cracked skin that may bleed", "Itching or burning"],
            "suggestions": ["Topical corticosteroids", "Salicylic acid", "Vitamin D analogues", "Phototherapy"]
        },
        {
            "problem": "adenitis",
            "symptoms": ["Swollen lymph nodes", "Tenderness in the neck or armpit", "Fever", "Redness"],
            "suggestions": ["Warm compress", "Ibuprofen", "Antibiotics (if bacterial)"]
        },
        {
            "problem": "appendicitis",
            "symptoms": ["Sudden pain in lower right abdomen", "Nausea", "Vomiting", "Loss of appetite", "Low fever"],
            "suggestions": ["Surgery (Appendectomy)"]
        },
        {
            "problem": "bursitis",
            "symptoms": ["Joint pain and stiffness", "Swelling", "Redness", "Warmth"],
            "suggestions": ["Rest", "Ice", "Ibuprofen", "Naproxen"]
        },
        {
            "problem": "cataracts",
            "symptoms": ["Cloudy or blurry vision", "Difficulty seeing at night", "Sensitivity to light/glare",
                         "Halos around lights"],
            "suggestions": ["Prescription glasses (early)", "Surgery (later stage)"]
        },
        {
            "problem": "dementia",
            "symptoms": ["Memory loss", "Difficulty communicating", "Disorientation", "Changes in personality"],
            "suggestions": ["Donepezil", "Memantine", "Cognitive therapy"]
        },
        {
            "problem": "eczema",
            "symptoms": ["Itchy skin", "Dry, cracked patches", "Small, raised bumps", "Skin thickening"],
            "suggestions": ["Topical corticosteroids", "Moisturizers", "Antihistamines"]
        },
        {
            "problem": "fibromyalgia",
            "symptoms": ["Widespread musculoskeletal pain", "Fatigue", "Sleep disturbances",
                         "Cognitive difficulties (fibro fog)"],
            "suggestions": ["Duloxetine", "Pregabalin", "Low-impact exercise"]
        },
        {
            "problem": "glaucoma",
            "symptoms": ["Gradual loss of peripheral vision", "Tunnel vision", "Severe eye pain (acute)",
                         "Blurred vision"],
            "suggestions": ["Prostaglandin analogs (eye drops)", "Beta-blocker eye drops"]
        },
        {
            "problem": "hernia",
            "symptoms": ["Bulge in abdominal wall or groin", "Pain when lifting", "Dull ache", "Feeling of fullness"],
            "suggestions": ["Support garments", "Surgery (for repair)"]
        },
        {
            "problem": "influenza",
            "symptoms": ["High fever", "Body aches", "Exhaustion", "Dry cough", "Sore throat", "Runny nose"],
            "suggestions": ["Oseltamivir (if early)", "Paracetamol", "Fluids"]
        },
        {
            "problem": "jaundice",
            "symptoms": ["Yellowing of skin and eyes", "Dark urine", "Pale stools", "Fatigue"],
            "suggestions": ["Treat the underlying liver condition"]
        },
        {
            "problem": "kidney stones",
            "symptoms": ["Severe pain in back/side", "Pain during urination", "Blood in urine", "Nausea"],
            "suggestions": ["Tamsulosin", "Painkillers (NSAIDs)", "Increased fluid intake"]
        },
        {
            "problem": "lupus",
            "symptoms": ["Butterfly-shaped rash on face", "Joint pain", "Fatigue", "Fever", "Sensitivity to sun"],
            "suggestions": ["Hydroxychloroquine", "Corticosteroids", "Immunosuppressants"]
        },
        {
            "problem": "meningitis",
            "symptoms": ["Sudden high fever", "Stiff neck", "Severe headache", "Sensitivity to light", "Confusion"],
            "suggestions": ["Antibiotics (urgent)", "IV fluids"]
        },
        {
            "problem": "narcolepsy",
            "symptoms": ["Excessive daytime sleepiness", "Sudden muscle weakness (cataplexy)", "Sleep paralysis"],
            "suggestions": ["Modafinil", "Stimulants", "Antidepressants"]
        },
        {
            "problem": "obesity",
            "symptoms": ["Excessive body fat", "Difficulty breathing", "Joint pain", "Sleep apnea"],
            "suggestions": ["Orlistat", "Liraglutide", "Lifestyle counseling"]
        },
        {
            "problem": "pharyngitis",
            "symptoms": ["Sore throat", "Difficulty swallowing", "Swollen glands", "Red tonsils"],
            "suggestions": ["Salt water gargle", "Lozenges", "Antibiotics (only if bacterial)"]
        },
        {
            "problem": "quinsy",
            "symptoms": ["Severe throat pain (one-sided)", "Muffled voice", "Swelling", "Difficulty opening mouth"],
            "suggestions": ["Surgical drainage", "Antibiotics (IV)"]
        },
        {
            "problem": "rhinitis",
            "symptoms": ["Sneezing", "Runny nose", "Congestion", "Itchy throat/nose"],
            "suggestions": ["Intranasal corticosteroids", "Antihistamines"]
        },
        {
            "problem": "scoliosis",
            "symptoms": ["Uneven shoulders", "Prominent shoulder blade", "Uneven waist", "Leaning to one side"],
            "suggestions": ["Bracing", "Physical therapy", "Surgery (severe cases)"]
        },
        {
            "problem": "alopecia",
            "symptoms": ["Patchy hair loss", "Sudden thinning", "Smooth, coin-sized patches"],
            "suggestions": ["Minoxidil", "Corticosteroid injections", "Anthralin"]
        },
        {
            "problem": "blepharitis",
            "symptoms": ["Red, swollen eyelids", "Crusty debris at base of eyelashes", "Itchy eyes",
                         "Gritty sensation"],
            "suggestions": ["Warm compresses", "Eyelid scrubs", "Antibiotic ointment"]
        },
        {
            "problem": "carpal tunnel syndrome",
            "symptoms": ["Numbness in thumb and fingers", "Tingling", "Weakness in hand", "Shock-like sensations"],
            "suggestions": ["Wrist splinting", "NSAIDs", "Corticosteroid injections"]
        },
        {
            "problem": "diverticulitis",
            "symptoms": ["Severe abdominal pain (lower left)", "Fever", "Nausea", "Change in bowel habits"],
            "suggestions": ["Antibiotics (oral)", "Liquid diet (acute phase)", "Pain management"]
        },
        {
            "problem": "emphysema",
            "symptoms": ["Shortness of breath", "Chronic cough", "Wheezing", "Chest tightness"],
            "suggestions": ["Inhaled bronchodilators", "Inhaled steroids", "Supplemental oxygen"]
        },
        {
            "problem": "folliculitis",
            "symptoms": ["Small red bumps around hair follicles", "Pus-filled blisters", "Itching", "Tenderness"],
            "suggestions": ["Antibacterial soap", "Warm compresses", "Topical mupirocin"]
        },
        {
            "problem": "gingivitis",
            "symptoms": ["Swollen gums", "Gums that bleed easily", "Bad breath", "Receding gums"],
            "suggestions": ["Antiseptic mouthwash", "Professional dental cleaning"]
        },
        {
            "problem": "hyperthyroidism",
            "symptoms": ["Unexplained weight loss", "Rapid heartbeat (tachycardia)", "Anxiety",
                         "Increased sensitivity to heat"],
            "suggestions": ["Methimazole", "Propylthiouracil", "Beta-blockers"]
        },
        {
            "problem": "impetigo",
            "symptoms": ["Red sores that break open", "Yellow-brown crusts", "Itchy rash", "Fluid-filled blisters"],
            "suggestions": ["Topical antibiotic cream (e.g., Mupirocin)", "Oral antibiotics"]
        },
        {
            "problem": "keratosis pilaris",
            "symptoms": ["Small, rough bumps (chicken skin)", "Dry, sandpaper-like skin", "Minor redness"],
            "suggestions": ["Exfoliating creams (lactic acid)", "Urea-based lotions"]
        },
        {
            "problem": "lichen planus",
            "symptoms": ["Purple, itchy, flat-topped bumps", "Lacy white patches in mouth", "Ridged nails"],
            "suggestions": ["Topical steroids", "Oral antihistamines", "Light therapy"]
        },
        {
            "problem": "myasthenia gravis",
            "symptoms": ["Drooping eyelids", "Double vision", "Difficulty swallowing", "Fatigue in limb muscles"],
            "suggestions": ["Pyridostigmine", "Immunosuppressants"]
        },
        {
            "problem": "nephritis",
            "symptoms": ["Blood in urine", "Swelling (edema) in face/legs", "High blood pressure", "Foamy urine"],
            "suggestions": ["Blood pressure medication (ACE inhibitors)", "Diuretics"]
        },
        {
            "problem": "osteomyelitis",
            "symptoms": ["Bone pain", "Fever", "Swelling/redness over the bone", "Fatigue"],
            "suggestions": ["Long-term IV antibiotics", "Surgical debridement"]
        },
        {
            "problem": "polycystic ovary syndrome (PCOS)",
            "symptoms": ["Irregular periods", "Excess hair growth (hirsutism)", "Acne", "Weight gain"],
            "suggestions": ["Metformin", "Birth control pills", "Anti-androgens"]
        },
        {
            "problem": "raynaud's disease",
            "symptoms": ["Cold fingers/toes", "Color changes in response to cold/stress", "Numbness", "Throbbing pain"],
            "suggestions": ["Calcium channel blockers", "Vasodilator creams"]
        },
        {
            "problem": "sarcoidosis",
            "symptoms": ["Persistent dry cough", "Shortness of breath", "Swollen lymph nodes", "Fatigue",
                         "Skin lesions"],
            "suggestions": ["Corticosteroids", "Immunosuppressants"]
        },
        {
            "problem": "trigeminal neuralgia",
            "symptoms": ["Sudden, severe, electric-shock-like face pain", "Triggered by touch or chewing"],
            "suggestions": ["Carbamazepine", "Gabapentin", "Phenytoin"]
        },
        {
            "problem": "ulcerative colitis",
            "symptoms": ["Bloody diarrhea", "Abdominal pain", "Urgent bowel movements", "Weight loss"],
            "suggestions": ["Aminosalicylates", "Corticosteroids", "Immunomodulators"]
        },
        {
            "problem": "vitiligo",
            "symptoms": ["Loss of skin color in blotches", "Premature whitening of hair",
                         "Loss of color in mouth tissues"],
            "suggestions": ["Topical corticosteroids", "Light therapy (PUVA)", "Depigmentation"]
        },
        {
            "problem": "amyotrophic lateral sclerosis (ALS)",
            "symptoms": ["Muscle weakness", "Twitching (fasciculations)", "Difficulty speaking or swallowing",
                         "Progressive loss of motor control"],
            "suggestions": ["Riluzole", "Edaravone", "Physical therapy"]
        },
        {
            "problem": "babesiosis",
            "symptoms": ["Fever", "Fatigue", "Hemolytic anemia", "Muscle aches"],
            "suggestions": ["Atovaquone", "Azithromycin"]
        },
        {
            "problem": "colitis (microscopic)",
            "symptoms": ["Chronic watery diarrhea", "Abdominal pain", "Weight loss"],
            "suggestions": ["Budesonide", "Antidiarrheal medications"]
        },
        {
            "problem": "delirium",
            "symptoms": ["Sudden confusion", "Disorientation", "Inability to focus", "Altered sleep-wake cycle"],
            "suggestions": ["Treat underlying cause (e.g., infection/medication review)",
                            "Low-dose antipsychotics (if necessary)"]
        },
        {
            "problem": "epididymitis",
            "symptoms": ["Pain and swelling in the scrotum", "Fever", "Discharge from penis", "Painful urination"],
            "suggestions": ["Ceftriaxone", "Doxycycline", "Scrotal support"]
        },
        {
            "problem": "fracture (stress)",
            "symptoms": ["Localized bone pain", "Swelling", "Pain during activity that stops with rest"],
            "suggestions": ["Rest (no weight-bearing)", "Crutches", "Analgesics"]
        },
        {
            "problem": "moebius syndrome",
            "symptoms": ["Facial paralysis", "Inability to move eyes laterally"],
            "suggestions": ["Speech therapy", "Reconstructive surgery"]
        },
        {
            "problem": "noonan syndrome",
            "symptoms": ["Short stature", "Heart defects", "Distinctive facial features"],
            "suggestions": ["Growth hormone", "Cardiac monitoring"]
        },
        {
            "problem": "osmotic demyelination syndrome",
            "symptoms": ["Confusion", "Difficulty speaking", "Motor impairment"],
            "suggestions": ["Correction of electrolyte balance"]
        },
        {
            "problem": "paroxysmal nocturnal hemoglobinuria",
            "symptoms": ["Dark urine", "Anemia", "Thrombosis"],
            "suggestions": ["Eculizumab", "Blood transfusions"]
        },
        {
            "problem": "quer'vain disease (thyroid)",
            "symptoms": ["Painful, tender thyroid gland"],
            "suggestions": ["NSAIDs", "Beta-blockers"]
        },
        {
            "problem": "reye syndrome",
            "symptoms": ["Confusion", "Seizures", "Vomiting"],
            "suggestions": ["Intravenous fluids", "Glucose (Emergency)"]
        },
        {
            "problem": "stiff-man syndrome",
            "symptoms": ["Progressive muscle rigidity"],
            "suggestions": ["Diazepam", "Physical therapy"]
        },
        {
            "problem": "thalamic pain syndrome",
            "symptoms": ["Severe pain", "Temperature sensitivity"],
            "suggestions": ["Antidepressants", "Anticonvulsants"]
        },
        {
            "problem": "uncharacterized inflammatory bowel disease",
            "symptoms": ["Abdominal pain", "Diarrhea", "Bleeding"],
            "suggestions": ["Mesalamine", "Immunomodulators"]
        },
        {
            "problem": "vici syndrome",
            "symptoms": ["Callosal agenesis", "Cataracts", "Cardiomyopathy"],
            "suggestions": ["Multidisciplinary supportive care"]
        },
        {
            "problem": "wiskott-aldrich syndrome",
            "symptoms": ["Eczema", "Low platelets", "Immunodeficiency"],
            "suggestions": ["Stem cell transplant", "IVIG"]
        },
        {
            "problem": "x-linked adrenoleukodystrophy",
            "symptoms": ["Behavioral changes", "Vision loss", "Muscle weakness"],
            "suggestions": ["Lorenzo's oil", "Hematopoietic cell transplant"]
        },
        {
            "problem": "yellow nail syndrome",
            "symptoms": ["Yellow nails", "Lymphedema", "Respiratory issues"],
            "suggestions": ["Diuretics", "Vitamin E"]
        },
        {
            "problem": "zieve syndrome",
            "symptoms": ["Hemolytic anemia", "Jaundice", "Hyperlipidemia"],
            "suggestions": ["Abstinence from alcohol"]
        },
        {
            "problem": "alport syndrome",
            "symptoms": ["Kidney failure", "Hearing loss", "Eye issues"],
            "suggestions": ["ACE inhibitors", "Kidney transplant"]
        },
        {
            "problem": "boutonneuse fever",
            "symptoms": ["Fever", "Rash", "Black spot at bite site"],
            "suggestions": ["Doxycycline"]
        },
        {
            "problem": "capillaritis",
            "symptoms": ["Reddish-brown pinpoint rash"],
            "suggestions": ["Topical steroids", "Compression stockings"]
        },
        {
            "problem": "dhat syndrome",
            "symptoms": ["Anxiety", "Fatigue", "Sexual preoccupation"],
            "suggestions": ["Counseling", "Psychotherapy"]
        },
        {
            "problem": "adenoid hypertrophy",
            "symptoms": ["Mouth breathing", "Snoring", "Recurrent ear infections"],
            "suggestions": ["Adenoidectomy", "Nasal steroid sprays"]
        },
        {
            "problem": "bicornuate uterus",
            "symptoms": ["Recurrent miscarriage", "Preterm labor"],
            "suggestions": ["Surgical correction (if indicated)", "Close monitoring"]
        },
        {
            "problem": "campomelic dysplasia",
            "symptoms": ["Bowed long bones", "Bell-shaped chest", "Respiratory distress"],
            "suggestions": ["Supportive respiratory care"]
        },
        {
            "problem": "duane retraction syndrome",
            "symptoms": ["Limited eye movement", "Eyeball retraction"],
            "suggestions": ["Strabismus surgery"]
        },
        {
            "problem": "erwinia infection",
            "symptoms": ["Rare opportunistic infection", "Localized inflammation"],
            "suggestions": ["Appropriate antibiotic therapy"]
        },
        {
            "problem": "filarial lymphedema",
            "symptoms": ["Severe swelling of limbs (elephantiasis)"],
            "suggestions": ["Antiparasitic meds", "Compression therapy"]
        },
        {
            "problem": "gardner syndrome",
            "symptoms": ["Multiple intestinal polyps", "Osteomas", "Skin tumors"],
            "suggestions": ["Regular colonoscopy", "Prophylactic surgery"]
        },
        {
            "problem": "hereditary spherocytosis",
            "symptoms": ["Anemia", "Jaundice", "Enlarged spleen"],
            "suggestions": ["Folic acid", "Splenectomy"]
        },
        {
            "problem": "icthyosis vulgaris",
            "symptoms": ["Dry, scaly skin on extremities"],
            "suggestions": ["Moisturizing creams", "Keratolytic agents"]
        },
        {
            "problem": "junctural tachycardia",
            "symptoms": ["Palpitations", "Lightheadedness", "Rapid heart rate"],
            "suggestions": ["Ablation", "Anti-arrhythmic drugs"]
        },
        {
            "problem": "keratoacanthoma",
            "symptoms": ["Rapidly growing, dome-shaped skin lesion"],
            "suggestions": ["Surgical excision", "Cryotherapy"]
        },
        {
            "problem": "loiasis",
            "symptoms": ["Eye worm migration", "Localized swelling (Calabar swellings)"],
            "suggestions": ["Diethylcarbamazine"]
        },
        {
            "problem": "macrodactyly",
            "symptoms": ["Abnormally large fingers or toes"],
            "suggestions": ["Epiphysiodesis", "Reconstructive surgery"]
        },
        {
            "problem": "necrotizing fasciitis",
            "symptoms": ["Severe pain", "Rapidly spreading skin discoloration"],
            "suggestions": ["Surgical debridement", "IV antibiotics (Emergency)"]
        },
        {
            "problem": "oculopharyngeal muscular dystrophy",
            "symptoms": ["Drooping eyelids", "Swallowing difficulties"],
            "suggestions": ["Eyelid surgery", "Swallowing therapy"]
        },
        {
            "problem": "pentalogy of cantrell",
            "symptoms": ["Congenital defects of heart/diaphragm/abdominal wall"],
            "suggestions": ["Complex surgical reconstruction"]
        },
        {
            "problem": "quer'vain syndrome (de Quervain's)",
            "symptoms": ["Pain at the base of the thumb and wrist"],
            "suggestions": ["Splinting", "Corticosteroid injections"]
        },
        {
            "problem": "rachischisis",
            "symptoms": ["Severe neural tube defect involving exposed spinal cord"],
            "suggestions": ["Surgical closure", "Supportive care"]
        },
        {
            "problem": "sotos syndrome",
            "symptoms": ["Rapid childhood growth", "Large head", "Learning delay"],
            "suggestions": ["Developmental support"]
        },
        {
            "problem": "trench mouth (Vincent's angina)",
            "symptoms": ["Painful, bleeding gums", "Foul breath"],
            "suggestions": ["Professional cleaning", "Antibiotics"]
        },
        {
            "problem": "urorectal septum malformation sequence",
            "symptoms": ["Incomplete separation of urogenital and anorectal tracts"],
            "suggestions": ["Multiple staged surgical corrections"]
        },
        {
            "problem": "van der woude syndrome",
            "symptoms": ["Cleft lip/palate", "Lip pits"],
            "suggestions": ["Surgical repair"]
        },
        {
            "problem": "weill-marchesani syndrome",
            "symptoms": ["Short stature", "Small spherical lenses (eyes)"],
            "suggestions": ["Lens surgery", "Regular eye exams"]
        },
        {
            "problem": "x-linked agammaglobulinemia",
            "symptoms": ["Recurrent severe bacterial infections"],
            "suggestions": ["Lifelong antibody replacement therapy"]
        },
        {
            "problem": "y-linked deafness",
            "symptoms": ["Hearing loss specifically passed through paternal line"],
            "suggestions": ["Hearing aids", "Cochlear implants"]
        },
        {
            "problem": "zuckerkandl organ tumor (Pheochromocytoma)",
            "symptoms": ["High blood pressure", "Headache", "Palpitations"],
            "suggestions": ["Surgical resection"]
        },
        {
            "problem": "apoplexy",
            "symptoms": ["Sudden loss of consciousness or paralysis"],
            "suggestions": ["Acute stroke management protocols"]
        },
        {
            "problem": "bronchiectasis",
            "symptoms": ["Chronic cough", "Thick mucus", "Recurrent infections"],
            "suggestions": ["Airway clearance", "Antibiotics"]
        },
        {
            "problem": "chorioretinitis",
            "symptoms": ["Inflammation of the choroid and retina", "Vision impairment"],
            "suggestions": ["Corticosteroids", "Antivirals (if applicable)"]
        },
        {
            "problem": "dermatitis herpetiformis",
            "symptoms": ["Extremely itchy, blister-like rash"],
            "suggestions": ["Dapsone", "Gluten-free diet"]
        },
        {
            "problem": "gangrene",
            "symptoms": ["Discoloration (black/blue)", "Loss of sensation", "Foul-smelling discharge",
                         "Severe pain followed by numbness"],
            "suggestions": ["Surgical debridement", "Intravenous antibiotics"]
        },
        {
            "problem": "hyperhidrosis",
            "symptoms": ["Excessive sweating (palms, soles, underarms) without heat or exercise"],
            "suggestions": ["Prescription antiperspirants (aluminum chloride)", "Iontophoresis", "Botox injections"]
        },
        {
            "problem": "ichthyosis",
            "symptoms": ["Dry, scaly skin", "Fish-scale appearance", "Cracked skin"],
            "suggestions": ["Keratolytic creams (lactic acid)", "Moisturizers (petrolatum)"]
        },
        {
            "problem": "kikuchi disease",
            "symptoms": ["Fever", "Swollen neck lymph nodes", "Night sweats", "Skin rash"],
            "suggestions": ["NSAIDs (for symptoms)", "Supportive care"]
        },
        {
            "problem": "leukemia",
            "symptoms": ["Fatigue", "Frequent infections", "Easy bruising or bleeding", "Bone pain"],
            "suggestions": ["Chemotherapy", "Targeted therapy", "Stem cell transplant"]
        },
        {
            "problem": "mastitis",
            "symptoms": ["Breast pain/redness", "Warmth", "Flu-like symptoms (fever/chills)"],
            "suggestions": ["Dicloxacillin (if infection)", "Warm compresses", "Frequent nursing/pumping"]
        },
        {
            "problem": "narcolepsy (type 2)",
            "symptoms": ["Excessive daytime sleepiness without cataplexy", "Sleep attacks"],
            "suggestions": ["Modafinil", "Armodafinil"]
        },
        {
            "problem": "optic neuritis",
            "symptoms": ["Sudden vision loss in one eye", "Pain with eye movement", "Color vision deficiency"],
            "suggestions": ["Intravenous corticosteroids"]
        },
        {
            "problem": "prostatitis",
            "symptoms": ["Painful ejaculation", "Pelvic pain", "Frequent urination", "Flu-like symptoms"],
            "suggestions": ["Antibiotics (e.g., Ciprofloxacin)", "Alpha-blockers"]
        },
        {
            "problem": "quadrantanopia",
            "symptoms": ["Loss of vision in one-quarter of the visual field", "Difficulty reading"],
            "suggestions": ["Treat underlying brain injury/stroke", "Vision therapy"]
        },
        {
            "problem": "rhabdomyolysis",
            "symptoms": ["Muscle pain", "Weakness", "Dark/tea-colored urine"],
            "suggestions": ["Aggressive IV fluids"]
        },
        {
            "problem": "syphilis",
            "symptoms": ["Painless sores (chancres)", "Skin rashes", "Swollen lymph nodes"],
            "suggestions": ["Penicillin G (intramuscular)"]
        },
        {
            "problem": "torticollis",
            "symptoms": ["Twisting of the neck", "Chin tilted to one side", "Headache", "Stiffness"],
            "suggestions": ["Physical therapy", "Botulinum toxin (Botox)", "Muscle relaxants"]
        },
        {
            "problem": "ulcer (peptic)",
            "symptoms": ["Burning stomach pain", "Feeling of fullness/bloating", "Intolerance to fatty foods"],
            "suggestions": ["PPIs (e.g., Omeprazole)", "Antibiotics (for H. pylori)"]
        },
        {
            "problem": "actinic keratosis",
            "symptoms": ["Rough, scaly patches on skin", "Small, crusty bump", "Itching or burning"],
            "suggestions": ["Cryotherapy", "Topical 5-fluorouracil", "Imiquimod cream"]
        },
        {
            "problem": "bacterial vaginosis",
            "symptoms": ["Thin gray or white discharge", "Fishy odor", "Itching", "Burning during urination"],
            "suggestions": ["Metronidazole (oral or gel)", "Clindamycin cream"]
        },
        {
            "problem": "capsulitis",
            "symptoms": ["Pain at base of toe/finger", "Swelling", "Feeling like walking on a pebble"],
            "suggestions": ["Taping", "Orthotic inserts", "NSAIDs"]
        },
        {
            "problem": "dermatomyositis",
            "symptoms": ["Violet-colored rash on eyelids/knuckles", "Muscle weakness", "Difficulty swallowing"],
            "suggestions": ["Corticosteroids", "Immunosuppressants (e.g., Methotrexate)"]
        },
        {
            "problem": "erysipelas",
            "symptoms": ["Red, swollen, painful rash", "Shiny skin", "Fever", "Chills"],
            "suggestions": ["Penicillin or other antibiotics"]
        },
        {
            "problem": "gastroparesis",
            "symptoms": ["Nausea", "Vomiting", "Early fullness after eating", "Abdominal pain"],
            "suggestions": ["Metoclopramide", "Erythromycin", "Dietary adjustments"]
        },
        {
            "problem": "hemophilia",
            "symptoms": ["Excessive bleeding from cuts", "Easy bruising", "Painful, swollen joints"],
            "suggestions": ["Clotting factor replacement therapy", "Desmopressin"]
        },
        {
            "problem": "interstitial cystitis",
            "symptoms": ["Chronic pelvic pain", "Frequent urge to urinate", "Pain during intercourse"],
            "suggestions": ["Pentosan polysulfate", "Antihistamines", "Bladder instillations"]
        },
        {
            "problem": "juvenile rheumatoid arthritis",
            "symptoms": ["Joint stiffness (especially morning)", "Joint swelling", "Fever", "Rash"],
            "suggestions": ["NSAIDs", "DMARDs (e.g., Methotrexate)", "Biologic agents"]
        },
        {
            "problem": "keloids",
            "symptoms": ["Raised, rubbery scars", "Itchiness", "Tenderness over scar tissue"],
            "suggestions": ["Silicone gel sheets", "Steroid injections", "Cryotherapy"]
        },
        {
            "problem": "listeriosis",
            "symptoms": ["Fever", "Muscle aches", "Nausea", "Diarrhea", "Stiff neck (in severe cases)"],
            "suggestions": ["Intravenous antibiotics (e.g., Ampicillin)"]
        },
        {
            "problem": "melanoma",
            "symptoms": ["New or changing skin spot", "Asymmetrical border", "Irregular color", "Increasing size"],
            "suggestions": ["Surgical excision", "Immunotherapy", "Targeted therapy"]
        },
        {
            "problem": "neutropenia",
            "symptoms": ["Frequent infections", "Mouth ulcers", "Skin abscesses", "Fever"],
            "suggestions": ["G-CSF (Granulocyte-colony stimulating factor)", "Antibiotics"]
        },
        {
            "problem": "orthostatic hypotension",
            "symptoms": ["Dizziness upon standing", "Blurred vision", "Fainting"],
            "suggestions": ["Fludrocortisone", "Midodrine"]
        },
        {
            "problem": "polymyalgia rheumatica",
            "symptoms": ["Pain and stiffness in shoulders/hips", "Morning stiffness >45 mins", "Weight loss"],
            "suggestions": ["Low-dose corticosteroids"]
        },
        {
            "problem": "q fever",
            "symptoms": ["High fever", "Severe headache", "Fatigue", "Muscle pain", "Dry cough"],
            "suggestions": ["Doxycycline"]
        },
        {
            "problem": "restless legs syndrome",
            "symptoms": ["Unpleasant crawling sensation in legs", "Urge to move legs", "Worse at night"],
            "suggestions": ["Dopamine agonists", "Gabapentin", "Iron supplements"]
        },
        {
            "problem": "scleroderma",
            "symptoms": ["Hardening/tightening of skin", "Cold sensitivity (Raynaud's)", "Heartburn"],
            "suggestions": ["Vasodilators", "Immunosuppressants", "PPIs for reflux"]
        },
        {
            "problem": "tachyarrhythmia",
            "symptoms": ["Rapid, irregular heartbeat", "Dizziness", "Shortness of breath", "Fainting"],
            "suggestions": ["Beta-blockers", "Anti-arrhythmic drugs", "Catheter ablation"]
        },
        {
            "problem": "urethritis",
            "symptoms": ["Burning sensation when urinating", "Discharge from urethra", "Itching/irritation"],
            "suggestions": ["Antibiotics (e.g., Azithromycin or Doxycycline)"]
        },
        {
            "problem": "aphasia",
            "symptoms": ["Difficulty speaking", "Trouble understanding speech", "Difficulty with reading/writing"],
            "suggestions": ["Speech-language therapy", "Augmentative communication devices"]
        },
        {
            "problem": "brucellosis",
            "symptoms": ["Fever", "Sweating", "Malaise", "Joint pain", "Fatigue"],
            "suggestions": ["Doxycycline", "Rifampin"]
        },
        {
            "problem": "cryoglobulinemia",
            "symptoms": ["Fatigue", "Joint pain", "Skin rashes", "Numbness in hands/feet"],
            "suggestions": ["Immunosuppressants", "Plasmapheresis", "Treat underlying Hepatitis C"]
        },
        {
            "problem": "dyshidrotic eczema",
            "symptoms": ["Small, itchy blisters on palms/soles", "Scaling", "Cracking"],
            "suggestions": ["High-potency topical steroids", "Moisturizers", "Cool compresses"]
        },
        {
            "problem": "epiglottitis",
            "symptoms": ["High fever", "Sore throat", "Difficulty swallowing", "Drooling", "Labored breathing"],
            "suggestions": ["Intravenous antibiotics", "Airway management (Emergency)"]
        },
        {
            "problem": "follicular lymphoma",
            "symptoms": ["Painless swollen lymph nodes", "Fatigue", "Night sweats", "Weight loss"],
            "suggestions": ["Rituximab", "Chemotherapy", "Radiation therapy"]
        },
        {
            "problem": "granulomatosis with polyangiitis",
            "symptoms": ["Sinus congestion", "Bloody nasal discharge", "Shortness of breath", "Joint pain"],
            "suggestions": ["Cyclophosphamide", "Corticosteroids", "Rituximab"]
        },
        {
            "problem": "hidradenitis suppurativa",
            "symptoms": ["Painful lumps under skin", "Abscesses", "Tunneling (sinus tracts)", "Scarring"],
            "suggestions": ["Adalimumab", "Topical antibiotics", "Surgical drainage"]
        },
        {
            "problem": "idiopathic thrombocytopenic purpura (ITP)",
            "symptoms": ["Easy bruising", "Petechiae (tiny red spots)", "Prolonged bleeding", "Nosebleeds"],
            "suggestions": ["Corticosteroids", "IVIG", "Splenectomy"]
        },
        {
            "problem": "juvenile dermatomyositis",
            "symptoms": ["Rash on eyelids/knuckles", "Proximal muscle weakness", "Abdominal pain"],
            "suggestions": ["Corticosteroids", "Methotrexate", "Physical therapy"]
        },
        {
            "problem": "kearns-sayre syndrome",
            "symptoms": ["Drooping eyelids", "Limited eye movement", "Hearing loss", "Muscle weakness"],
            "suggestions": ["Coenzyme Q10", "Supportive cardiac/endocrine management"]
        },
        {
            "problem": "leprosy (Hansen's disease)",
            "symptoms": ["Discolored skin patches", "Numbness in affected areas", "Muscle weakness"],
            "suggestions": ["Multi-drug therapy (Dapsone, Rifampicin, Clofazimine)"]
        },
        {
            "problem": "myositis",
            "symptoms": ["Muscle weakness", "Muscle pain", "Fatigue", "Difficulty climbing stairs"],
            "suggestions": ["Corticosteroids", "Immunosuppressants"]
        },
        {
            "problem": "nodular scleritis",
            "symptoms": ["Severe eye pain", "Red, raised nodules on the eye", "Blurred vision"],
            "suggestions": ["Topical steroids", "Oral NSAIDs", "Systemic immunosuppressants"]
        },
        {
            "problem": "orchitis",
            "symptoms": ["Testicular pain/swelling", "Fever", "Nausea", "Discharge"],
            "suggestions": ["Antibiotics (if bacterial)", "Pain relievers", "Scrotal support"]
        },
        {
            "problem": "pyoderma gangrenosum",
            "symptoms": ["Painful, rapidly expanding ulcers with purple borders"],
            "suggestions": ["Corticosteroids", "Cyclosporine", "Wound care"]
        },
        {
            "problem": "q fever endocarditis",
            "symptoms": ["Prolonged fever", "Fatigue", "Heart murmur", "Night sweats"],
            "suggestions": ["Long-term antibiotic therapy (Doxycycline + Hydroxychloroquine)"]
        },
        {
            "problem": "reflex sympathetic dystrophy (CRPS)",
            "symptoms": ["Intense burning pain", "Swelling", "Color changes in skin", "Sensitivity to touch"],
            "suggestions": ["Gabapentin", "Physical therapy", "Nerve blocks"]
        },
        {
            "problem": "stiff-person syndrome",
            "symptoms": ["Muscle stiffness", "Painful muscle spasms", "Heightened sensitivity to stimuli"],
            "suggestions": ["Benzodiazepines (e.g., Diazepam)", "Baclofen", "IVIG"]
        },
        {
            "problem": "toxic epidermal necrolysis (TEN)",
            "symptoms": ["Widespread skin redness", "Blistering", "Skin sloughing off", "Fever"],
            "suggestions": ["Hospitalization (ICU/Burn unit)", "Discontinuation of causative drugs"]
        },
        {
            "problem": "amyloidosis",
            "symptoms": ["Fatigue", "Swelling in legs/ankles", "Shortness of breath", "Numbness in hands"],
            "suggestions": ["Chemotherapy", "Stem cell transplant", "Targeted protein stabilizers"]
        },
        {
            "problem": "bartonellosis",
            "symptoms": ["Fever", "Fatigue", "Swollen lymph nodes", "Skin lesions"],
            "suggestions": ["Azithromycin", "Doxycycline"]
        },
        {
            "problem": "candidiasis (invasive)",
            "symptoms": ["High fever", "Chills", "Fatigue", "Organ-specific symptoms (if systemic)"],
            "suggestions": ["Fluconazole", "Echinocandins (IV)"]
        },
        {
            "problem": "dermatomyositis (amyopathic)",
            "symptoms": ["Skin rash characteristic of dermatomyositis without significant muscle weakness"],
            "suggestions": ["Sun protection", "Hydroxychloroquine", "Topical corticosteroids"]
        },
        {
            "problem": "empyema",
            "symptoms": ["Chest pain", "Fever", "Shortness of breath", "Cough"],
            "suggestions": ["Antibiotics", "Chest tube drainage (thoracostomy)"]
        },
        {
            "problem": "foamy virus infection (simian)",
            "symptoms": ["Often asymptomatic in humans", "Potential for mild respiratory illness"],
            "suggestions": ["Monitoring", "Supportive care"]
        },
        {
            "problem": "goodpasture syndrome",
            "symptoms": ["Coughing up blood", "Shortness of breath", "Dark urine", "Fatigue"],
            "suggestions": ["Plasmapheresis", "Corticosteroids", "Cyclophosphamide"]
        },
        {
            "problem": "histoplasmosis",
            "symptoms": ["Fever", "Dry cough", "Chest pain", "Joint pain"],
            "suggestions": ["Itraconazole", "Amphotericin B (severe)"]
        },
        {
            "problem": "inclusion body myositis",
            "symptoms": ["Progressive weakness in quadriceps and finger flexors", "Muscle atrophy",
                         "Difficulty falling"],
            "suggestions": ["Physical therapy", "Occupational therapy"]
        },
        {
            "problem": "jeune syndrome",
            "symptoms": ["Narrow chest", "Short ribs", "Respiratory distress in infancy"],
            "suggestions": ["Supportive respiratory care", "Chest surgery (in some cases)"]
        },
        {
            "problem": "kawasaki disease",
            "symptoms": ["High fever (>5 days)", "Red eyes", "Strawberry tongue", "Swollen hands/feet", "Rash"],
            "suggestions": ["IVIG", "High-dose Aspirin"]
        },
        {
            "problem": "leukodystrophy",
            "symptoms": ["Loss of motor skills", "Difficulty walking", "Vision/hearing loss", "Speech delay"],
            "suggestions": ["Physical therapy", "Bone marrow transplant (if early)"]
        },
        {
            "problem": "mononeuritis multiplex",
            "symptoms": ["Sudden onset of weakness/numbness in two or more nerve areas"],
            "suggestions": ["Treat the underlying vasculitis or autoimmune cause"]
        },
        {
            "problem": "niemann-pick disease",
            "symptoms": ["Enlarged liver/spleen", "Developmental delay", "Poor motor coordination"],
            "suggestions": ["Supportive care", "Miglustat (for some types)"]
        },
        {
            "problem": "osteogenesis imperfecta",
            "symptoms": ["Brittle bones (frequent fractures)", "Blue sclera (eyes)", "Hearing loss"],
            "suggestions": ["Bisphosphonates", "Physical therapy", "Surgical rod placement"]
        },
        {
            "problem": "pemphigus vulgaris",
            "symptoms": ["Painful blisters on skin and mucous membranes"],
            "suggestions": ["Corticosteroids", "Rituximab", "Mycophenolate"]
        },
        {
            "problem": "q fever (chronic)",
            "symptoms": ["Persistent fatigue", "Weight loss", "Heart valve inflammation"],
            "suggestions": ["Long-term combination antibiotics (years)"]
        },
        {
            "problem": "renal tubular acidosis",
            "symptoms": ["Muscle weakness", "Bone pain", "Kidney stones", "Growth retardation (in children)"],
            "suggestions": ["Bicarbonate supplements", "Potassium citrate"]
        },
        {
            "problem": "sturge-weber syndrome",
            "symptoms": ["Port-wine birthmark on face", "Seizures", "Glaucoma"],
            "suggestions": ["Anticonvulsants", "Laser therapy for birthmark", "Glaucoma drops"]
        },
        {
            "problem": "thrombotic thrombocytopenic purpura (TTP)",
            "symptoms": ["Fever", "Confusion", "Purpura", "Anemia symptoms"],
            "suggestions": ["Plasma exchange (Plasmapheresis)", "Corticosteroids"]
        },
        {
            "problem": "acanthosis nigricans",
            "symptoms": ["Dark, velvety skin in body folds"],
            "suggestions": ["Treat underlying insulin resistance", "Topical retinoids"]
        },
        {
            "problem": "ankyloglossia",
            "symptoms": ["Short or tight lingual frenulum (tongue-tie)"],
            "suggestions": ["Frenotomy (minor surgery)", "Speech therapy"]
        },
        {
            "problem": "barrett's esophagus",
            "symptoms": ["Heartburn, acid regurgitation"],
            "suggestions": ["PPI therapy", "Endoscopic monitoring"]
        },
        {
            "problem": "cataplexy",
            "symptoms": ["Sudden muscle weakness triggered by emotion"],
            "suggestions": ["Sodium oxybate", "Antidepressants"]
        },
        {
            "problem": "diabetic retinopathy",
            "symptoms": ["Blurred vision, floaters, vision loss"],
            "suggestions": ["Blood sugar control", "Laser surgery"]
        },
        {
            "problem": "epiphyseal dysplasia",
            "symptoms": ["Joint pain, short stature, early arthritis"],
            "suggestions": ["Pain management", "Orthopedic monitoring"]
        },
        {
            "problem": "fibrodysplasia ossificans progressiva",
            "symptoms": ["Soft tissue turning to bone"],
            "suggestions": ["Pain management", "Prevent trauma"]
        },
        {
            "problem": "galactosemia",
            "symptoms": ["Jaundice, vomiting, failure to thrive"],
            "suggestions": ["Strict galactose-free diet"]
        },
        {
            "problem": "hemosiderosis",
            "symptoms": ["Organ dysfunction due to iron buildup"],
            "suggestions": ["Chelation therapy", "Phlebotomy"]
        },
        {
            "problem": "ileocolitis",
            "symptoms": ["Diarrhea, abdominal pain (Crohn's related)"],
            "suggestions": ["Corticosteroids", "Immunomodulators"]
        },
        {
            "problem": "jejunitis",
            "symptoms": ["Abdominal pain, nausea, weight loss"],
            "suggestions": ["Antibiotics (if bacterial)", "Dietary adjustment"]
        },
        {
            "problem": "kuru",
            "symptoms": ["Tremors, loss of coordination, dementia"],
            "suggestions": ["Supportive care"]
        },
        {
            "problem": "leukoplakia",
            "symptoms": ["White patches in mouth"],
            "suggestions": ["Biopsy", "Cessation of tobacco/alcohol"]
        },
        {
            "problem": "myositis ossificans",
            "symptoms": ["Hard lump in muscle, pain"],
            "suggestions": ["Physical therapy", "Avoid overexertion"]
        },
        {
            "problem": "nystagmus",
            "symptoms": ["Involuntary rhythmic eye movement"],
            "suggestions": ["Corrective lenses", "Surgery on eye muscles"]
        },
        {
            "problem": "osteochondritis dissecans",
            "symptoms": ["Joint pain, locking or catching in joint"],
            "suggestions": ["Rest, physical therapy, surgery"]
        },
        {
            "problem": "polymyositis",
            "symptoms": ["Weakness in proximal muscles"],
            "suggestions": ["Corticosteroids", "Immunosuppressants"]
        },
        {
            "problem": "quer'vain tenosynovitis",
            "symptoms": ["Pain near base of thumb"],
            "suggestions": ["Thumb spica splint", "NSAIDs"]
        },
        {
            "problem": "rhabdomyoma",
            "symptoms": ["Often asymptomatic, or obstructive symptoms"],
            "suggestions": ["Surgical removal"]
        },
        {
            "problem": "syringomyelia",
            "symptoms": ["Back pain, weakness, loss of pain sensation"],
            "suggestions": ["Surgery to drain cyst"]
        },
        {
            "problem": "trichotillomania",
            "symptoms": ["Recurrent urge to pull out hair"],
            "suggestions": ["Cognitive behavioral therapy"]
        },
        {
            "problem": "uveitis",
            "symptoms": ["Eye redness, pain, light sensitivity"],
            "suggestions": ["Steroid eye drops"]
        },
        {
            "problem": "vasculitis",
            "symptoms": ["Fever, fatigue, weight loss, organ-specific pain"],
            "suggestions": ["Corticosteroids", "Immunosuppressants"]
        },
        {
            "problem": "wernicke encephalopathy",
            "symptoms": ["Confusion, eye movement issues, ataxia"],
            "suggestions": ["Thiamine (Vitamin B1) injection"]
        },
        {
            "problem": "xeroderma pigmentosum",
            "symptoms": ["Extreme sensitivity to UV light"],
            "suggestions": ["Strict sun avoidance", "Protective clothing"]
        },
        {
            "problem": "yaws",
            "symptoms": ["Skin sores, bone pain"],
            "suggestions": ["Single-dose Azithromycin"]
        },
        {
            "problem": "zika virus",
            "symptoms": ["Fever, rash, joint pain, conjunctivitis"],
            "suggestions": ["Rest, fluids, acetaminophen"]
        },
        {
            "problem": "adenomyosis",
            "symptoms": ["Heavy, painful menstruation"],
            "suggestions": ["Hormonal IUDs", "Pain relievers"]
        },
        {
            "problem": "bunion",
            "symptoms": ["Bony bump at base of big toe"],
            "suggestions": ["Roomy shoes, orthotics, surgery"]
        },
        {
            "problem": "croup",
            "symptoms": ["Barking cough, hoarseness"],
            "suggestions": ["Humidified air, corticosteroids"]
        },
        {
            "problem": "amyoplasia",
            "symptoms": ["Congenital joint contractures, muscle weakness"],
            "suggestions": ["Physical therapy, serial casting"]
        },
        {
            "problem": "beriberi",
            "symptoms": ["Muscle wasting, loss of sensation, heart failure"],
            "suggestions": ["Thiamine supplementation"]
        },
        {
            "problem": "choreoathetosis",
            "symptoms": ["Involuntary dance-like movements"],
            "suggestions": ["Dopamine-depleting agents"]
        },
        {
            "problem": "dyskeratosis congenita",
            "symptoms": ["Abnormal skin pigmentation, nail dystrophy"],
            "suggestions": ["Bone marrow stimulants, stem cell transplant"]
        },
        {
            "problem": "ebstein anomaly",
            "symptoms": ["Cyanosis, fatigue, heart murmur"],
            "suggestions": ["Surgical repair, arrhythmia management"]
        },
        {
            "problem": "fanconi anemia",
            "symptoms": ["Bone marrow failure, physical abnormalities"],
            "suggestions": ["Stem cell transplant, androgen therapy"]
        },
        {
            "problem": "glycogen storage disease",
            "symptoms": ["Enlarged liver, low blood sugar, muscle weakness"],
            "suggestions": ["Frequent feedings, cornstarch regimen"]
        },
        {
            "problem": "homocystinuria",
            "symptoms": ["Vision problems, skeletal abnormalities, developmental delay"],
            "suggestions": ["Vitamin B6, B12, and folate supplements"]
        },
        {
            "problem": "insuloma",
            "symptoms": ["Severe hypoglycemia, dizziness, confusion"],
            "suggestions": ["Surgical resection"]
        },
        {
            "problem": "jansen metaphyseal chondrodysplasia",
            "symptoms": ["Short stature, bowed limbs, hypercalcemia"],
            "suggestions": ["Bisphosphonates, orthopedic surgery"]
        },
        {
            "problem": "kikuchi-fujimoto disease",
            "symptoms": ["Fever, tender lymphadenopathy"],
            "suggestions": ["Supportive care, NSAIDs"]
        },
        {
            "problem": "leber congenital amaurosis",
            "symptoms": ["Severe vision loss at birth, nystagmus"],
            "suggestions": ["Gene therapy"]
        }
]



    result = None
    searched_problem = ""

    available_conditions = [
        item["problem"]
        for item in medicines
    ]

    if request.method == "POST":

        searched_problem = request.form.get("problem", "").strip()
        result = None

        for item in medicines:

            if searched_problem.lower() in item["problem"].lower():
                result = {
                    "symptoms": item.get("symptoms", []),
                    "suggestions": item.get("suggestions", [])
                }

                # 🔥 SAVE TO DATABASE
                conn = get_db()
                cur = conn.cursor()

                cur.execute("""
                                    INSERT INTO history (
                                        user_id,
                                        username,
                                        problem,
                                        symptoms,
                                        suggestions,
                                        searched_at
                                    )
                                    VALUES (%s, %s, %s, %s, %s, NOW())
                                """, (
                    session.get("user_id"),
                    session["username"],
                    searched_problem,
                    json.dumps(result["symptoms"]),
                    json.dumps(result["suggestions"])
                ))

                conn.commit()
                cur.close()
                conn.close()

                break

    return render_template(
        "medicine.html",
        result=result,
        searched_problem=searched_problem,
        available_conditions=available_conditions
    )

@app.route("/history")
@login_required
def history():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT * FROM history 
        WHERE username = %s 
        ORDER BY searched_at DESC
    """, (session["username"],))

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("history.html", records=records)

@app.route("/download-history")
@login_required
def download_history():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute( "SELECT problem, suggestions, symptoms, searched_at FROM history WHERE user_id = %s ORDER BY searched_at DESC", (session["user_id"],) )
        records = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        records = []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Problem", "Suggestions", "Symptoms", "Searched At"])
    for r in records:
        writer.writerow([r["problem"], r["suggestions"], r["symptoms"], r["searched_at"]])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=my_health_history.csv"}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("auth_stage") == "complete" and "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    prefill = session.get("admin_prefill", "")
    is_superadmin = False
    if prefill:
        acc = admin_db.session.query(AdminAccount).filter_by(username=prefill).first()
        is_superadmin = acc.role == "superadmin" if acc else False

    from flask import get_flashed_messages as _gfm
    messages = _gfm(with_categories=True)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin_account = admin_db.session.query(AdminAccount).filter_by(username=username).first()
        if admin_account and admin_account.check_password(password):
            session.pop("admin_prefill", None)
            session["admin_id"] = admin_account.id
            session["admin_username"] = admin_account.username
            session["admin_display"] = admin_account.display_name
            session["admin_role"] = admin_account.role
            if admin_account.has_2fa():
                session["auth_stage"] = "password_ok"
                return redirect(url_for("admin_verify_2fa"))
            else:
                session["auth_stage"] = "complete"
                return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "error")
        messages = [("error", "Invalid username or password.")]

    return render_template(
        "admin/login.html",
        prefill_username=prefill,
        is_superadmin=is_superadmin,
        messages=messages,
    )


@app.route("/admin/verify-2fa")
def admin_verify_2fa():
    if "admin_id" not in session:
        return redirect(url_for("signin"))
    if session.get("auth_stage") == "complete":
        return redirect(url_for("admin_dashboard"))
    admin = get_admin_account()
    has_pin = bool(admin and admin.pin_hash)
    has_webauthn = bool(admin and admin.webauthn_credential_id)
    return render_template(
        "admin/verify_2fa.html",
        has_pin=has_pin,
        has_webauthn=has_webauthn,
        webauthn_available=WEBAUTHN_AVAILABLE,
    )


@app.route("/admin/verify-pin", methods=["POST"])
def admin_verify_pin():
    if "admin_id" not in session:
        return redirect(url_for("signin"))
    admin = get_admin_account()
    pin = request.form.get("pin", "")
    if admin and admin.check_pin(pin):
        session["auth_stage"] = "complete"
        return redirect(url_for("admin_dashboard"))
    flash("Incorrect PIN. Please try again.", "error")
    return redirect(url_for("admin_verify_2fa"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_display", None)
    session.pop("admin_role", None)
    session.pop("auth_stage", None)
    return redirect(url_for("signin"))


# ── Security (own account) ─────────────────────────────────────────────────────

@app.route("/admin/security", methods=["GET"])
@admin_panel_login_required
def admin_security():
    admin = get_admin_account()
    return render_template(
        "admin/security.html", admin=admin, webauthn_available=WEBAUTHN_AVAILABLE
    )


@app.route("/admin/setup-pin", methods=["POST"])
@admin_panel_login_required
def admin_setup_pin():
    admin = get_admin_account()
    pin = request.form.get("pin", "")
    confirm = request.form.get("confirm_pin", "")
    if len(pin) < 4 or len(pin) > 8:
        flash("PIN must be 4–8 digits.", "error")
        return redirect(url_for("admin_security"))
    if pin != confirm:
        flash("PINs do not match.", "error")
        return redirect(url_for("admin_security"))
    if not pin.isdigit():
        flash("PIN must contain digits only.", "error")
        return redirect(url_for("admin_security"))
    admin.pin_hash = _bcrypt.hashpw(pin.encode(), _bcrypt.gensalt()).decode()
    admin_db.session.commit()
    flash("PIN set up successfully.", "success")
    return redirect(url_for("admin_security"))


@app.route("/admin/remove-pin", methods=["POST"])
@admin_panel_login_required
def admin_remove_pin():
    admin = get_admin_account()
    admin.pin_hash = None
    admin_db.session.commit()
    flash("PIN removed.", "success")
    return redirect(url_for("admin_security"))


# ── WebAuthn ───────────────────────────────────────────────────────────────────

@app.route("/admin/webauthn/register-options", methods=["POST"])
@admin_panel_login_required
def admin_webauthn_register_options():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({"error": "WebAuthn not available"}), 500
    admin = get_admin_account()
    opts = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name="AdminPanel",
        user_id=str(admin.id).encode(),
        user_name=admin.username,
        user_display_name=admin.display_name or admin.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
    )
    session["webauthn_reg_challenge"] = bytes_to_base64url(opts.challenge)
    import webauthn as _wa
    return jsonify(json.loads(_wa.options_to_json(opts)))


@app.route("/admin/webauthn/register-verify", methods=["POST"])
@admin_panel_login_required
def admin_webauthn_register_verify():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({"error": "WebAuthn not available"}), 500
    admin = get_admin_account()
    try:
        challenge = base64url_to_bytes(session.get("webauthn_reg_challenge", ""))
        credential = request.json
        verification = verify_registration_response(
            credential=credential,
            expected_rp_id=get_rp_id(),
            expected_origin=get_origin(),
            expected_challenge=challenge,
            require_user_verification=True,
        )
        admin.webauthn_credential_id = bytes_to_base64url(verification.credential_id)
        admin.webauthn_public_key = bytes_to_base64url(verification.credential_public_key)
        admin.webauthn_sign_count = verification.sign_count
        admin_db.session.commit()
        return jsonify({"verified": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/webauthn/auth-options", methods=["POST"])
def admin_webauthn_auth_options():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({"error": "WebAuthn not available"}), 500
    admin_id = session.get("admin_id")
    if not admin_id:
        return jsonify({"error": "Not authenticated"}), 401
    admin = admin_db.session.get(AdminAccount, admin_id)
    if not admin or not admin.webauthn_credential_id:
        return jsonify({"error": "No credential registered"}), 400
    opts = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(admin.webauthn_credential_id))
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session["webauthn_auth_challenge"] = bytes_to_base64url(opts.challenge)
    import webauthn as _wa
    return jsonify(json.loads(_wa.options_to_json(opts)))


@app.route("/admin/webauthn/auth-verify", methods=["POST"])
def admin_webauthn_auth_verify():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({"error": "WebAuthn not available"}), 500
    admin_id = session.get("admin_id")
    if not admin_id:
        return jsonify({"error": "Not authenticated"}), 401
    admin = admin_db.session.get(AdminAccount, admin_id)
    try:
        challenge = base64url_to_bytes(session.get("webauthn_auth_challenge", ""))
        credential = request.json
        verification = verify_authentication_response(
            credential=credential,
            expected_rp_id=get_rp_id(),
            expected_origin=get_origin(),
            expected_challenge=challenge,
            credential_public_key=base64url_to_bytes(admin.webauthn_public_key),
            credential_current_sign_count=admin.webauthn_sign_count,
            require_user_verification=True,
        )
        admin.webauthn_sign_count = verification.new_sign_count
        admin_db.session.commit()
        session["auth_stage"] = "complete"
        return jsonify({"verified": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/webauthn/remove", methods=["POST"])
@admin_panel_login_required
def admin_webauthn_remove():
    admin = get_admin_account()
    admin.webauthn_credential_id = None
    admin.webauthn_public_key = None
    admin.webauthn_sign_count = 0
    admin_db.session.commit()
    flash("Biometric credential removed.", "success")
    return redirect(url_for("admin_security"))


# ── Superadmin panel ───────────────────────────────────────────────────────────

@app.route("/admin/superadmin")
@admin_superadmin_required
def admin_superadmin_panel():
    admins = admin_db.session.query(AdminAccount).order_by(AdminAccount.role.desc(), AdminAccount.id).all()
    return render_template("admin/superadmin.html", admins=admins)


@app.route("/admin/superadmin/admin/<int:admin_id>/reset-password", methods=["POST"])
@admin_superadmin_required
def admin_sa_reset_password(admin_id):
    target = admin_db.session.get(AdminAccount, admin_id)
    if not target:
        flash("Admin not found.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    if target.role == "superadmin" and target.id != session["admin_id"]:
        flash("Cannot change another superadmin's password.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    new_pw = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    if new_pw != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    target.password_hash = _bcrypt.hashpw(new_pw.encode(), _bcrypt.gensalt()).decode()
    admin_db.session.commit()
    flash(f"Password updated for {target.display_name}.", "success")
    return redirect(url_for("admin_superadmin_panel"))


@app.route("/admin/superadmin/admin/<int:admin_id>/reset-pin", methods=["POST"])
@admin_superadmin_required
def admin_sa_reset_pin(admin_id):
    target = admin_db.session.get(AdminAccount, admin_id)
    if not target:
        flash("Admin not found.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    new_pin = request.form.get("new_pin", "")
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        flash("PIN must be 4–8 digits.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    target.pin_hash = _bcrypt.hashpw(new_pin.encode(), _bcrypt.gensalt()).decode()
    admin_db.session.commit()
    flash(f"PIN updated for {target.display_name}.", "success")
    return redirect(url_for("admin_superadmin_panel"))


@app.route("/admin/superadmin/admin/<int:admin_id>/remove-pin", methods=["POST"])
@admin_superadmin_required
def admin_sa_remove_pin(admin_id):
    target = admin_db.session.get(AdminAccount, admin_id)
    if not target:
        flash("Admin not found.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    target.pin_hash = None
    admin_db.session.commit()
    flash(f"PIN removed for {target.display_name}.", "success")
    return redirect(url_for("admin_superadmin_panel"))


@app.route("/admin/superadmin/admin/<int:admin_id>/remove-biometric", methods=["POST"])
@admin_superadmin_required
def admin_sa_remove_biometric(admin_id):
    target = admin_db.session.get(AdminAccount, admin_id)
    if not target:
        flash("Admin not found.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    target.webauthn_credential_id = None
    target.webauthn_public_key = None
    target.webauthn_sign_count = 0
    admin_db.session.commit()
    flash(f"Biometric removed for {target.display_name}.", "success")
    return redirect(url_for("admin_superadmin_panel"))


@app.route("/admin/superadmin/admin/<int:admin_id>/delete", methods=["POST"])
@admin_superadmin_required
def admin_sa_delete_admin(admin_id):
    target = admin_db.session.get(AdminAccount, admin_id)
    if not target:
        flash("Admin not found.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    if target.role == "superadmin":
        flash("Cannot remove a superadmin account.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    if target.id == session["admin_id"]:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_superadmin_panel"))
    admin_db.session.delete(target)
    admin_db.session.commit()
    flash(f"Admin '{target.display_name}' has been removed.", "success")
    return redirect(url_for("admin_superadmin_panel"))


# ── Dashboard & data pages ─────────────────────────────────────────────────────

def _make_user(row, search_count=0):
    """Wrap a real 'users' table row into a dot-accessible object for templates."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role="user",
        status="active",
        search_count=search_count,
        created_at=row["created_at"],
    )


def _make_search(row):
    """Wrap a real 'history' table row into a dot-accessible object for templates."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=row["id"],
        user_id=row["user_id"],
        problem=row["problem"],
        category="general",
        results_count="-",
        searched_at=row["searched_at"],
        user=SimpleNamespace(username=row["username"] or ""),
    )


@app.route("/admin/dashboard")
@admin_panel_login_required
def admin_dashboard():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM history")
        total_searches = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM history
            WHERE searched_at >= NOW() - INTERVAL '30 days' AND user_id IS NOT NULL
        """)
        active_30 = cur.fetchone()[0]

        cur.execute("""
            SELECT DATE(searched_at) AS day, COUNT(*) AS cnt
            FROM history
            WHERE searched_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(searched_at)
        """)
        day_map = {str(r["day"]): r["cnt"] for r in cur.fetchall()}

        daily_counts, labels = [], []
        for i in range(29, -1, -1):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).date()
            labels.append(day.strftime("%b %d"))
            daily_counts.append(day_map.get(str(day), 0))

        cur.execute("""
            SELECT problem, COUNT(*) AS cnt
            FROM history
            GROUP BY problem
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_keywords = [(r["problem"], r["cnt"]) for r in cur.fetchall()]

        cur.execute("""
            SELECT problem AS category, COUNT(*) AS cnt
            FROM history
            GROUP BY problem
            ORDER BY cnt DESC
            LIMIT 10
        """)
        category_counts = [(r["category"], r["cnt"]) for r in cur.fetchall()]

        cur.close()
        conn.close()
    except Exception:
        total_users = total_searches = active_30 = 0
        daily_counts = [0] * 30
        labels = [(datetime.now(timezone.utc) - timedelta(days=i)).strftime("%b %d") for i in range(29, -1, -1)]
        top_keywords = []
        category_counts = []

    avg_searches = round(total_searches / total_users, 1) if total_users else 0
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_searches=total_searches,
        avg_searches=avg_searches,
        active_30=active_30,
        daily_counts=json.dumps(daily_counts),
        labels=json.dumps(labels),
        top_keywords=top_keywords,
        category_counts=category_counts,
    )


@app.route("/admin/users")
@admin_panel_login_required
def admin_users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    per_page = 15
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        where = ""
        params = []
        if search:
            where = "WHERE username ILIKE %s OR email ILIKE %s"
            params = [f"%{search}%", f"%{search}%"]

        cur.execute(f"SELECT COUNT(*) FROM users {where}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        )
        rows = cur.fetchall()

        user_list = []
        for row in rows:
            cur.execute("SELECT COUNT(*) FROM history WHERE user_id = %s", (row["id"],))
            sc = cur.fetchone()[0]
            user_list.append(_make_user(row, sc))

        cur.close()
        conn.close()
    except Exception:
        total = 0
        user_list = []

    return render_template(
        "admin/users.html",
        users=user_list,
        pagination=AdminPaginator(user_list, page, per_page, total),
        search=search,
        status_filter="",
    )


@app.route("/admin/users/export")
@admin_panel_login_required
def admin_export_users():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cur.fetchall()
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["ID", "Username", "Email", "Joined"])
        for row in rows:
            cur.execute("SELECT COUNT(*) FROM history WHERE user_id = %s", (row["id"],))
            sc = cur.fetchone()[0]
            w.writerow([row["id"], row["username"], row["email"], row["created_at"].strftime("%Y-%m-%d")])
        cur.close()
        conn.close()
        out.seek(0)
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=users.csv"})
    except Exception:
        return "Export failed", 500


@app.route("/admin/users/<int:user_id>")
@admin_panel_login_required
def admin_user_detail(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        urow = cur.fetchone()
        if not urow:
            cur.close(); conn.close()
            return "User not found", 404

        cur.execute("SELECT COUNT(*) FROM history WHERE user_id = %s", (user_id,))
        sc = cur.fetchone()[0]
        user = _make_user(urow, sc)

        cur.execute("""
            SELECT problem AS category, COUNT(*) AS cnt
            FROM history WHERE user_id = %s
            GROUP BY problem ORDER BY cnt DESC LIMIT 10
        """, (user_id,))
        cat_breakdown = [(r["category"], r["cnt"]) for r in cur.fetchall()]

        cur.execute("""
            SELECT * FROM history
            WHERE user_id = %s AND searched_at >= NOW() - INTERVAL '30 days'
            ORDER BY searched_at DESC LIMIT 20
        """, (user_id,))
        recent = [_make_search(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT DATE(searched_at) AS day, COUNT(*) AS cnt
            FROM history WHERE user_id = %s
            AND searched_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(searched_at)
        """, (user_id,))
        day_map = {str(r["day"]): r["cnt"] for r in cur.fetchall()}

        daily_counts, labels = [], []
        for i in range(29, -1, -1):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).date()
            labels.append(day.strftime("%b %d"))
            daily_counts.append(day_map.get(str(day), 0))

        cur.close()
        conn.close()
    except Exception:
        return "Error loading user", 500

    return render_template(
        "admin/admin_user_detail.html",
        user=user,
        category_breakdown=cat_breakdown,
        recent_searches=recent,
        daily_counts=json.dumps(daily_counts),
        labels=json.dumps(labels),
    )


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_panel_login_required
def admin_delete_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            flash("User not found.", "error")
            cur.close(); conn.close()
            return redirect(url_for("admin_users"))
        username = row["username"]
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        flash(f"User '{username}' has been deleted.", "success")
    except Exception:
        flash("Failed to delete user.", "error")
    return redirect(url_for("admin_users"))


@app.route("/admin/search-history")
@admin_panel_login_required
def admin_search_history():
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "").strip()
    per_page = 20
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        where = ""
        params = []
        if search_term:
            where = "WHERE h.problem ILIKE %s"
            params = [f"%{search_term}%"]

        cur.execute(
            f"SELECT COUNT(*) FROM history h {where}", params
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""SELECT h.*, u.username AS uname FROM history h
                LEFT JOIN users u ON u.id = h.user_id
                {where}
                ORDER BY h.searched_at DESC LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        rows = cur.fetchall()
        searches = []
        for r in rows:
            from types import SimpleNamespace
            s = SimpleNamespace(
                id=r["id"],
                user_id=r["user_id"],
                problem=r["problem"],
                category="general",
                results_count="-",
                searched_at=r["searched_at"],
                user=SimpleNamespace(username=r["uname"] or r["username"] or ""),
            )
            searches.append(s)

        cur.close()
        conn.close()
    except Exception:
        total = 0
        searches = []

    return render_template(
        "admin/search_history.html",
        searches=searches,
        pagination=AdminPaginator(searches, page, per_page, total),
        search=search_term,
        category="",
        categories=[],
    )


@app.route("/admin/search-history/export")
@admin_panel_login_required
def admin_export_searches():
    fmt = request.args.get("format", "csv")
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT h.id, h.username, h.problem, h.searched_at,
                   u.username AS uname
            FROM history h
            LEFT JOIN users u ON u.id = h.user_id
            ORDER BY h.searched_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        rows = []

    if fmt == "json":
        data = [
            {
                "id": r["id"],
                "username": r["uname"] or r["username"] or "",
                "problem": r["problem"],
                "searched_at": r["searched_at"].isoformat() if r["searched_at"] else "",
            }
            for r in rows
        ]
        return Response(json.dumps(data, indent=2), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=search_history.json"})

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID", "Username", "Problem", "Searched At"])
    for r in rows:
        w.writerow([
            r["id"],
            r["uname"] or r["username"] or "",
            r["problem"],
            r["searched_at"].strftime("%Y-%m-%d %H:%M") if r["searched_at"] else "",
        ])
    out.seek(0)
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=search_history.csv"})


if __name__ == "__main__":
    init_db()
    with app.app_context():
        admin_db.create_all()
        seed_admin_panel()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)