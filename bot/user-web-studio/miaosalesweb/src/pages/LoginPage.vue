<template>
  <q-layout view="hHh lpR fFf" class="login-layout">
    <q-page-container>
      <q-page class="flex flex-center">
        <q-card class="login-card q-pa-lg">
          <q-card-section class="text-center">
            <div class="text-h5 text-weight-medium">Miao Sales</div>
            <div class="text-caption text-grey-7 q-mt-xs">Mock 登录（本地验证，不调用后台）</div>
          </q-card-section>

          <q-card-section>
            <q-form @submit.prevent="onSubmit">
              <q-input
                v-model="username"
                label="用户名"
                outlined
                dense
                autocomplete="username"
                :rules="[(val) => !!val || '请输入用户名']"
              />
              <q-input
                v-model="password"
                label="密码"
                type="password"
                outlined
                dense
                class="q-mt-md"
                autocomplete="current-password"
                :rules="[(val) => !!val || '请输入密码']"
              />
              <q-btn
                type="submit"
                color="primary"
                label="登录"
                class="full-width q-mt-lg"
                :loading="loading"
                unelevated
              />
            </q-form>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth-store';
import { useChatStore } from 'stores/chat-store';

const router = useRouter();
const authStore = useAuthStore();
const chatStore = useChatStore();

const username = ref('');
const password = ref('');
const loading = ref(false);

async function onSubmit() {
  if (!username.value.trim() || !password.value) return;
  loading.value = true;
  try {
    authStore.login(username.value, password.value);
    chatStore.initForUser();
    await router.push('/chat');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
.login-layout {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%);
  min-height: 100vh;
}

.login-card {
  width: 100%;
  max-width: 400px;
  border-radius: 12px;
}
</style>
