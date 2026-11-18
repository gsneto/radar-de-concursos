import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { RouteErrorFallback } from '@/components/ui/error-boundary';
import { Shell } from './shell';

const MyContestsPage = lazy(() =>
  import('@/features/my-contests/MyContestsPage').then((m) => ({ default: m.MyContestsPage })),
);
const OverviewPage = lazy(() =>
  import('@/features/overview/OverviewPage').then((m) => ({ default: m.OverviewPage })),
);
const OpportunitiesPage = lazy(() =>
  import('@/features/opportunities/OpportunitiesPage').then((m) => ({ default: m.OpportunitiesPage })),
);
const DossierPage = lazy(() =>
  import('@/features/dossier/DossierPage').then((m) => ({ default: m.DossierPage })),
);
const DeadlinesPage = lazy(() =>
  import('@/features/deadlines/DeadlinesPage').then((m) => ({ default: m.DeadlinesPage })),
);
const StudiesPage = lazy(() =>
  import('@/features/studies/StudiesPage').then((m) => ({ default: m.StudiesPage })),
);
const HistoryPage = lazy(() =>
  import('@/features/history/HistoryPage').then((m) => ({ default: m.HistoryPage })),
);
const SettingsPage = lazy(() =>
  import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
const OperationPage = lazy(() =>
  import('@/features/operation/OperationPage').then((m) => ({ default: m.OperationPage })),
);
const ReviewPage = lazy(() =>
  import('@/features/review/ReviewPage').then((m) => ({ default: m.ReviewPage })),
);
const IdentityPage = lazy(() =>
  import('@/features/identity/IdentityPage').then((m) => ({ default: m.IdentityPage })),
);
const PipelinePage = lazy(() =>
  import('@/features/pipeline/PipelinePage').then((m) => ({ default: m.PipelinePage })),
);
const MesaPage = lazy(() =>
  import('@/features/mesa/MesaPage').then((m) => ({ default: m.MesaPage })),
);
const PlansPage = lazy(() =>
  import('@/features/account/PlansAndAuthPage').then((m) => ({ default: m.PlansPage })),
);
const AccountPage = lazy(() =>
  import('@/features/account/PlansAndAuthPage').then((m) => ({ default: m.AccountPage })),
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    errorElement: <RouteErrorFallback />,
    children: [
      { index: true, element: <MyContestsPage />, handle: { title: 'Meus Concursos' } },
      { path: 'visao-geral', element: <OverviewPage />, handle: { title: 'Visão geral & Métricas' } },
      {
        path: 'oportunidades',
        element: <OpportunitiesPage />,
        handle: { title: 'Radar de Concursos', crumb: 'Radar' },
      },
      {
        path: 'dossie/:contestId',
        element: <DossierPage />,
        handle: { title: 'Dossiê', crumb: 'Concursos' },
      },
      { path: 'prazos', element: <DeadlinesPage />, handle: { title: 'Prazos' } },
      { path: 'planos', element: <PlansPage />, handle: { title: 'Planos & Acesso Pro', crumb: 'Planos' } },
      { path: 'conta', element: <AccountPage />, handle: { title: 'Minha Conta', crumb: 'Conta' } },
      { path: 'revisao', element: <ReviewPage />, handle: { title: 'Revisão' } },
      { path: 'mesa', element: <MesaPage />, handle: { title: 'Mesa' } },
      { path: 'identidades', element: <IdentityPage />, handle: { title: 'Identidades' } },
      { path: 'pipeline', element: <PipelinePage />, handle: { title: 'Pipeline documental' } },
      { path: 'estudos/*', element: <StudiesPage />, handle: { title: 'Estudos' } },
      { path: 'historico', element: <HistoryPage />, handle: { title: 'Histórico' } },
      { path: 'configuracoes', element: <SettingsPage />, handle: { title: 'Configurações' } },
      { path: 'operacao', element: <OperationPage />, handle: { title: 'Operação' } },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
