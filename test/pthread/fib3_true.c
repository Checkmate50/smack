#include <pthread.h>

int x = 1;
int y = 1;

void *t1(void *arg)
{
  x += y;
  x += y;
  x += y;

  pthread_exit(NULL);
}

void *t2(void *arg)
{
  y += x;
  y += x;
  y += x;

  pthread_exit(NULL);
}

int main() {
  __SMACK_code("assume (forall i:int :: $pthreadStatus[i][0] == $pthread_uninitialized);");
  pthread_t tid1, tid2;
  pthread_create(&tid1, NULL, t1, NULL);
  pthread_create(&tid2, NULL, t2, NULL);
  assert(x <= 21 && y <= 21);
}