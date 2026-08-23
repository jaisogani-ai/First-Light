/* Standalone correctness test for pcc_crypto.c against known SHA-256/HMAC-SHA256 test
** vectors (RFC 6234 / RFC 4231). Compiles independently of cFE:
**   gcc -o test_pcc_crypto test_pcc_crypto.c pcc_crypto.c && ./test_pcc_crypto
*/
#include "pcc_crypto.h"
#include <stdio.h>
#include <string.h>

static int check_hex(const uint8_t *actual, const char *expected_hex, const char *label) {
    char buf[65];
    for (int i = 0; i < 32; i++) sprintf(buf + i * 2, "%02x", actual[i]);
    buf[64] = 0;
    int ok = strcmp(buf, expected_hex) == 0;
    printf("%s: %s\n  got:      %s\n  expected: %s\n", label, ok ? "PASS" : "FAIL", buf, expected_hex);
    return ok;
}

int main(void) {
    int all_ok = 1;
    uint8_t out[32];

    PCC_SHA256((const uint8_t *)"", 0, out);
    all_ok &= check_hex(out, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA256('')");

    PCC_SHA256((const uint8_t *)"abc", 3, out);
    all_ok &= check_hex(out, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA256('abc')");

    /* RFC 4231 Test Case 1: key=0x0b*20, data="Hi There" */
    uint8_t key[20]; memset(key, 0x0b, 20);
    PCC_HMAC_SHA256(key, 20, (const uint8_t *)"Hi There", 8, out);
    all_ok &= check_hex(out, "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", "HMAC-SHA256(RFC4231 Case 1)");

    printf(all_ok ? "\nALL VECTORS PASSED\n" : "\nSOME VECTORS FAILED\n");
    return all_ok ? 0 : 1;
}
