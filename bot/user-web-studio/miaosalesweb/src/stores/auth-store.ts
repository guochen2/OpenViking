import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

const AUTH_STORAGE_KEY = 'miaosales_auth';

interface AuthState {
  username: string;
}

function loadAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthState;
  } catch {
    return null;
  }
}

export const useAuthStore = defineStore('auth', () => {
  const saved = loadAuth();
  const username = ref(saved?.username ?? '');

  const isLoggedIn = computed(() => username.value.length > 0);
  const userId = computed(() => username.value);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function login(name: string, _password: string) {
    username.value = name.trim();
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ username: username.value }));
  }

  function logout() {
    username.value = '';
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }

  return {
    username,
    userId,
    isLoggedIn,
    login,
    logout,
  };
});
