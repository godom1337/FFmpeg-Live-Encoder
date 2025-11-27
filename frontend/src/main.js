import { mount } from 'svelte';
import AppWithRouter from './AppWithRouter.svelte';  // Custom router for Svelte 5

const app = mount(AppWithRouter, {
  target: document.getElementById('app')
});

export default app;