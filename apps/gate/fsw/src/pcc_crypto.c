/*
** Self-contained SHA-256 / HMAC-SHA256 implementation (public-domain algorithm, written
** independently for this project — no external crypto library dependency, matching the
** minimal-dependency style of a cFS flight app).
*/

#include "pcc_crypto.h"
#include <string.h>

static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_transform(uint32_t state[8], const uint8_t block[64]) {
    uint32_t w[64], a, b, c, d, e, f, g, h, t1, t2;
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i*4] << 24) | ((uint32_t)block[i*4+1] << 16) |
               ((uint32_t)block[i*4+2] << 8) | ((uint32_t)block[i*4+3]);
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(w[i-15], 7) ^ ROTR(w[i-15], 18) ^ (w[i-15] >> 3);
        uint32_t s1 = ROTR(w[i-2], 17) ^ ROTR(w[i-2], 19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=state[0]; b=state[1]; c=state[2]; d=state[3]; e=state[4]; f=state[5]; g=state[6]; h=state[7];
    for (int i = 0; i < 64; i++) {
        uint32_t s1 = ROTR(e,6) ^ ROTR(e,11) ^ ROTR(e,25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        t1 = h + s1 + ch + K[i] + w[i];
        uint32_t s0 = ROTR(a,2) ^ ROTR(a,13) ^ ROTR(a,22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        t2 = s0 + maj;
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    state[0]+=a; state[1]+=b; state[2]+=c; state[3]+=d;
    state[4]+=e; state[5]+=f; state[6]+=g; state[7]+=h;
}

void PCC_SHA256(const uint8_t *data, size_t len, uint8_t out[32]) {
    uint32_t state[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    uint64_t bitlen = (uint64_t)len * 8;
    size_t full_blocks = len / 64;

    for (size_t i = 0; i < full_blocks; i++) {
        sha256_transform(state, data + i * 64);
    }

    uint8_t block[128];
    size_t rem = len - full_blocks * 64;
    memcpy(block, data + full_blocks * 64, rem);
    block[rem++] = 0x80;
    size_t pad_to = (rem <= 56) ? 56 : 120;
    memset(block + rem, 0, pad_to - rem);
    for (int i = 0; i < 8; i++) {
        block[pad_to + i] = (uint8_t)(bitlen >> (56 - 8 * i));
    }
    size_t total = pad_to + 8;
    for (size_t off = 0; off < total; off += 64) {
        sha256_transform(state, block + off);
    }

    for (int i = 0; i < 8; i++) {
        out[i*4]   = (uint8_t)(state[i] >> 24);
        out[i*4+1] = (uint8_t)(state[i] >> 16);
        out[i*4+2] = (uint8_t)(state[i] >> 8);
        out[i*4+3] = (uint8_t)(state[i]);
    }
}

void PCC_HMAC_SHA256(const uint8_t *key, size_t key_len, const uint8_t *data, size_t data_len, uint8_t out[32]) {
    uint8_t key_block[64] = {0};
    if (key_len > 64) {
        PCC_SHA256(key, key_len, key_block);
    } else {
        memcpy(key_block, key, key_len);
    }

    uint8_t ipad[64], opad[64];
    for (int i = 0; i < 64; i++) {
        ipad[i] = key_block[i] ^ 0x36;
        opad[i] = key_block[i] ^ 0x5c;
    }

    /* Reference verifier scope: certificate payloads here are well under 4KB. A flight build
       would size this from the actual max certificate length rather than a fixed buffer. */
    uint8_t inner_input[64 + 4096];
    size_t inner_len = 64 + data_len;
    memcpy(inner_input, ipad, 64);
    memcpy(inner_input + 64, data, data_len);
    uint8_t inner_hash[32];
    PCC_SHA256(inner_input, inner_len, inner_hash);

    uint8_t outer_input[96];
    memcpy(outer_input, opad, 64);
    memcpy(outer_input + 64, inner_hash, 32);
    PCC_SHA256(outer_input, 96, out);
}
