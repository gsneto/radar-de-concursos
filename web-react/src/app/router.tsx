import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Shell } from './shell';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { OpportunitiesPage } from '@/features/opportunities/OpportunitiesPage';
import { DossierPage } from '@/features/dossier/DossierPage';
import { DeadlinesPage } from '@/features/deadlines/DeadlinesPage';
import { StudiesPage } from '@/features/studies/StudiesPage';
import { HistoryPage } from '@/features/history/HistoryPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { OperationPage } from '@/features/operation/OperationPage';
import { ReviewPage } from '@/features/review/ReviewPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <OverviewPage />, handle: { title: 'Visão geral' } },
      {
        path: 'oportunidades',
        element: <OpportunitiesPage />,
        handle: { title: 'Oportunidades', crumb: 'Oportunidades' },
      },
      {
        path: 'dossie/:contestId',
        element: <DossierPage />,
        handle: { title: 'Dossiê', crumb: 'Oportunidades' },
      },
      { path: 'prazos', element: <DeadlinesPage />, handle: { title: 'Prazos' } },
      { path: 'revisao', element: <ReviewPage />, handle: { title: 'Revisão' } },
      { path: 'estudos/*', element: <StudiesPage />, handle: { title: 'Estudos' } },
      { path: 'historico', element: <HistoryPage />, handle: { title: 'Histórico' } },
      { path: 'configuracoes', element: <SettingsPage />, handle: { title: 'Configurações' } },
      { path: 'operacao', element: <OperationPage />, handle: { title: 'Operação' } },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
