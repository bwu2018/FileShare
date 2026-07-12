CHUNK_SIZE = 1200  # raw ciphertext bytes per chunk; 1200 = 400*3, base64-encodes to 1600 chars, no padding
KEY_SIZE = 32     # AES-256 key
NONCE_SIZE = 12    # standard AES-GCM nonce (96 bits)
