CHUNK_SIZE = 189  # raw ciphertext bytes per chunk; 189 = 63*3, base64-encodes to 252 chars, no padding
KEY_SIZE = 32     # AES-256 key
NONCE_SIZE = 12    # standard AES-GCM nonce (96 bits)
