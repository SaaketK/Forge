/* leak.c — week-4 smoke test.
 * Obvious memory leak: make_buffer allocates 256 bytes; main reads from the
 * buffer and returns 1 without freeing it on the early-return path.
 */
#include <stdlib.h>

char* make_buffer(void) {
    char* buf = malloc(256);
    if (!buf) return NULL;
    return buf;
}

int main(void) {
    char* b = make_buffer();
    if (b == NULL) return 2;
    if (b[0] == 'x') return 1;  /* leak: no free(b) on this path */
    free(b);
    return 0;
}
