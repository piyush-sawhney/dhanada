<script setup lang="ts">
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">Dhanada</h1>
        <p class="mt-2 text-sm text-gray-500">Client Relationship Management</p>
      </div>
      <div class="rounded-xl bg-white p-8 shadow-sm ring-1 ring-gray-200">
        <slot />
      </div>
    </div>
  </div>
</template>
