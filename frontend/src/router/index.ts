import { createRouter, createWebHistory } from 'vue-router';
import AppLayout from '../components/layout/AppLayout.vue';
import HistoryView from '../views/HistoryView.vue';
import PredictLabView from '../views/PredictLabView.vue';
import ArchiveReviewView from '../views/ArchiveReviewView.vue';
import SandboxView from '../views/SandboxView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/history',
      children: [
        {
          path: 'history',
          name: 'History',
          component: HistoryView,
          meta: { title: '走势看板 - SSQ Quant' },
        },
        {
          path: 'predict',
          name: 'PredictLab',
          component: PredictLabView,
          meta: { title: '预测实验 - SSQ Quant' },
        },
        {
          path: 'archive',
          name: 'ArchiveReview',
          component: ArchiveReviewView,
          meta: { title: '预测档案 - SSQ Quant' },
        },
        {
          path: 'sandbox',
          name: 'Sandbox',
          component: SandboxView,
          meta: { title: '碰撞沙盒 - SSQ Quant' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/history',
    },
  ],
});

router.afterEach((to) => {
  if (to.meta.title) {
    document.title = to.meta.title as string;
  }
});

export default router;
