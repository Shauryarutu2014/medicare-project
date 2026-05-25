import os
import json
import random
import csv
import io
from datetime import datetime
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "medicare-dev-secret-key-2024")


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
    conn = psycopg2.connect(DATABASE_URL)
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

        # ── Check if admin credentials ──────────────────────────────────────
        if username in ADMIN_USERS and check_password_hash(ADMIN_USERS[username], password):
            session.clear()
            session["is_admin"] = True
            session["admin_username"] = username
            session["admin_display"] = ADMIN_DISPLAY.get(username, username)
            return redirect(url_for("admin_dashboard"))
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
        cur.execute("SELECT COUNT(*) as cnt FROM history WHERE user_id = %s", (session["user_id"],))
        history_count = cur.fetchone()["cnt"]
        cur.execute(
            "SELECT * FROM history WHERE user_id = %s ORDER BY searched_at DESC LIMIT 3",
            (session["user_id"],)
        )
        recent = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        history_count = 0
        total_users = 0
        recent = []
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

        for item in medicines:

            if item["problem"].lower() == searched_problem.lower():
                result = {
                    "symptoms": item.get("symptoms", []),
                    "suggestions": item.get("suggestions", [])
                }

                conn = get_db()
                cur = conn.cursor()

                cur.execute("""
                INSERT INTO history (
                    username,
                    datetime,
                    problem,
                    symptoms,
                    suggestions,
                    searched_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                """, (
                    session["username"],
                    str(datetime.now()),
                    searched_problem,
                    json.dumps(result.get("symptoms", [])),
                    json.dumps(result.get("suggestions", []))
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
    try:
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

    except Exception as e:
        print("HISTORY ERROR:", e)
        records = []

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


# ─── Hidden Admin Routes ───────────────────────────────────────────────────────
# These routes do NOT appear in the public UI. No links, no menus, no hints.

@app.route("/admin")
@admin_required
def admin_dashboard():

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ========================
    # TOTAL USERS
    # ========================
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    # ========================
    # TOTAL HISTORY
    # ========================
    cur.execute("SELECT COUNT(*) FROM history")
    total_history = cur.fetchone()[0]

    # ========================
    # WEEK SEARCHES
    # ========================
    cur.execute("""
        SELECT COUNT(*)
        FROM history
        WHERE searched_at >= NOW() - INTERVAL '7 days'
    """)
    week_searches = cur.fetchone()[0]

    # ========================
    # TOP ACTIVE USERS
    # ========================
    cur.execute("""
        SELECT users.username, COUNT(history.id) AS cnt
        FROM history
        JOIN users ON history.user_id = users.id
        GROUP BY users.username
        ORDER BY cnt DESC
        LIMIT 5
    """)

    top_users = []
    for row in cur.fetchall():
        top_users.append({
            "username": row[0],
            "cnt": row[1]
        })

    # ========================
    # TOP CONDITIONS
    # ========================
    cur.execute("""
        SELECT problem, COUNT(*) AS cnt
        FROM history
        GROUP BY problem
        ORDER BY cnt DESC
        LIMIT 5
    """)

    top_conditions = []
    for row in cur.fetchall():
        top_conditions.append({
            "problem": row[0],
            "cnt": row[1]
        })

    # ========================
    # ALL USERS (FOR TABLE)
    # ========================
    cur.execute("""
        SELECT id, username, email, created_at, password_hash
        FROM users
        ORDER BY id ASC
    """)

    users = []
    for row in cur.fetchall():
        users.append({
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "created_at": row[3],
            "password_hash": row[4]
        })

    # ========================
    # CLOSE DB
    # ========================
    cur.close()
    conn.close()

    # ========================
    # RENDER TEMPLATE
    # ========================
    return render_template(
        "admin_dashboard.html",
        admin_name=session.get("admin_display"),

        total_users=total_users,
        total_history=total_history,
        week_searches=week_searches,

        top_users=top_users,
        top_conditions=top_conditions,

        users=users
    )

@app.route("/admin/users")
def admin_users():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT username, email, created_at, password_hash
        FROM users
        ORDER BY created_at DESC
    """)

    users = cur.fetchall()

    cur.close()
    conn.close()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM history")
    total_history = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return render_template(
        "admin_users.html",
        users=users
    )

@app.route("/admin/history")
def admin_history():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT username, problem, symptoms, suggestions, searched_at
        FROM history
        ORDER BY searched_at DESC
    """)

    history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_history.html",
        history=history
    )

@app.route("/admin/download/users")
@admin_required
def admin_download_users():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, username, email, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        users = []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Username", "Email", "Created At"])
    for u in users:
        writer.writerow([u["id"], u["username"], u["email"], u["created_at"]])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=medicare_users.csv"}
    )


@app.route("/admin/download/history")
@admin_required
def admin_download_history():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM history ORDER BY searched_at DESC")
        records = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        records = []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Username", "Problem", "Suggestions", "Symptoms",  "Searched At"])
    for r in records:
        writer.writerow([r["id"], r["username"], r["problem"], r["suggestions"], r["symptoms"], r["searched_at"]])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=medicare_history.csv"}
    )


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
