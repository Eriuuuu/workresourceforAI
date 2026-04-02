<template>
  <div>
    <!-- 原始 HTML -->
    <p>Using mustaches: {{ rawHtml }}</p>
    <p>Using v-html directive: <span v-html="rawHtml"></span></p>
    
    <!-- 属性绑定 -->
    <div :id="dynamicId"></div>
    <button :disabled="isButtonDisabled">按钮</button>
    
    <!-- 动态绑定多个属性 -->
    <div v-bind="objectOfAttrs"></div>
    
    <!-- 类绑定 -->
    <div :class="{ active: isActive, 'text-danger': hasError }"></div>
    <div :class="[activeClass, errorClass]"></div>
    <div :class="[isActive ? activeClass : '', errorClass]"></div>
    
    <!-- 样式绑定 -->
    <div :style="{ color: activeColor, fontSize: fontSize + 'px' }"></div>
    <div :style="[baseStyles, overridingStyles]"></div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const rawHtml = ref('<span style="color: red">This should be red.</span>')
const dynamicId = ref('my-id')
const isButtonDisabled = ref(false)

const objectOfAttrs = reactive({
  id: 'container',
  class: 'wrapper',
  'data-type': 'component'
})

const isActive = ref(true)
const hasError = ref(false)
const activeClass = ref('active')
const errorClass = ref('text-danger')

const activeColor = ref('red')
const fontSize = ref(30)
const baseStyles = reactive({
  color: 'red',
  fontSize: '13px'
})
const overridingStyles = reactive({
  color: 'blue'
})
</script>