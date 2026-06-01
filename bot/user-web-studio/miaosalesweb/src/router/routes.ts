import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: () => import('pages/LoginPage.vue'),
  },
  {
    path: '/chat',
    component: () => import('pages/ChatPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/',
    redirect: '/chat',
  },

  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
