<script setup lang="ts">
import { computed, type Component } from "vue"
import { useRoute, RouterView } from "vue-router"
import AuthLayout from "./components/AuthLayout.vue"

const route = useRoute()
const layout = computed<Component>(() => {
  return (route.meta.layout as Component | undefined) ?? AuthLayout
})
</script>

<template>
  <RouterView>
    <template #default="{ Component: viewComponent }">
      <component :is="layout">
        <component :is="viewComponent" />
      </component>
    </template>
  </RouterView>
</template>
