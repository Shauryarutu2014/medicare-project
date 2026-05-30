try:
    import bcrypt
    # Salt for cost 12
    salt = bcrypt.gensalt(rounds=12)
    # Hash for "1234"
    hash_value = bcrypt.hashpw(b"1234", salt)
    print(hash_value.decode('utf-8'))
except ImportError:
    print("bcrypt library not available")