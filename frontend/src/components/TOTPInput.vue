<script setup lang="ts">
import { shallowRef, ref, watch } from "vue"

const model = defineModel<string>({ required: true })
const digits = ref<string[]>(["", "", "", "", "", ""])
const inputs = shallowRef<HTMLInputElement[]>([])

watch(digits, (val) => {
  model.value = val.join("")
}, { deep: true })

watch(model, (val) => {
  if (!val) digits.value = ["", "", "", "", "", ""]
})

function focusNext(index: number) {
  if (index < 5) inputs.value[index + 1]?.focus()
}

function focusPrev(index: number) {
  if (index > 0) inputs.value[index - 1]?.focus()
}

function handleInput(index: number) {
  if (digits.value[index]) focusNext(index)
}

function handleKeydown(index: number, e: KeyboardEvent) {
  if (e.key === "Backspace" && !digits.value[index]) focusPrev(index)
}

function handlePaste(e: ClipboardEvent) {
  const text = e.clipboardData?.getData("text") ?? ""
  const chars = text.replace(/\D/g, "").split("").slice(0, 16)
  chars.forEach((ch, i) => {
    if (i < 6) digits.value[i] = ch
  })
  requestAnimationFrame(() => inputs.value[Math.min(chars.length - 1, 5)]?.focus())
}

function setRef(el: unknown, index: number) {
  if (el instanceof HTMLInputElement) {
    inputs.value[index] = el
  }
}
</script>

<template>
  <div class="flex justify-center gap-2">
    <input
      v-for="i in 6"
      :key="i"
      :ref="(el: unknown) => setRef(el, i - 1)"
      v-model="digits[i - 1]"
      type="text"
      inputmode="numeric"
      maxlength="1"
      autocomplete="one-time-code"
      class="h-12 w-10 rounded-lg border border-gray-300 text-center text-lg font-semibold focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
      @input="handleInput(i - 1)"
      @keydown="handleKeydown(i - 1, $event)"
      @paste="handlePaste"
    />
  </div>
</template>
