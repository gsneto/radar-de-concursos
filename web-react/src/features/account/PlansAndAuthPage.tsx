import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Award,
  BookOpen,
  Check,
  Compass,
  Crown,
  KeyRound,
  Lock,
  LogOut,
  ShieldCheck,
  Sparkles,
  UserCheck,
  UserPlus,
  Webhook,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { keys, useAdminBilling, useAdminUsers, useAuthMe } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { api } from '@/lib/api';
import { type AppUser, useWorkspaceMode } from '@/lib/auth';

const SHOWCASE_CARDS = [
  {
    src: '/flashcards/fc-port-jotta-01.jpg',
    title: 'Português · Sessão x Cessão x Seção',
  },
  {
    src: '/flashcards/fc-bd-01.jpg',
    title: 'Banco de Dados · 1ª FN x 2ª FN x 3ª FN',
  },
  {
    src: '/flashcards/fc-seg-01.jpg',
    title: 'Segurança · Sigilo x Assinatura x Hash',
  },
  {
    src: '/flashcards/fc-sql-01.jpg',
    title: 'SQL · DELETE x TRUNCATE x DROP',
  },
];

const PLAN_LABELS: Record<string, string> = {
  free: 'Gratuito (Degustação)',
  pro: 'Plano Pro',
  founder: 'Passe Fundador TI',
};

export function PlansPage() {
  const navigate = useNavigate();
  const authMe = useAuthMe();
  const user = authMe.data?.user ?? null;
  const checkoutUrl = authMe.data?.checkout_url || '';

  const handleSelectPlan = (plan: 'free' | 'pro' | 'founder') => {
    if (plan === 'free') {
      navigate(user ? '/estudos/aulas' : '/conta');
      return;
    }
    if (checkoutUrl) {
      const sep = checkoutUrl.includes('?') ? '&' : '?';
      const emailParam = user?.email ? `&email=${encodeURIComponent(user.email)}` : '';
      window.open(`${checkoutUrl}${sep}plan=${plan}${emailParam}`, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate(`/conta?plano=${plan}`);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Plataforma Comercial · GSN Concursos"
        title="Tudo que você precisa para passar em Concursos Públicos de TI"
        description="Editais auditados para Sistemas de Informação, flashcards ilustrados por IA no estilo sketchnote, aulas em 5 etapas, ciclo semanal automático e banco de questões com gabarito comentado."
      />

      {/* Hero Comercial */}
      <section className="relative overflow-hidden rounded-2xl border border-amber-400/30 bg-surface p-6 sm:p-8 shadow-xl">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-500/15 via-transparent to-transparent"
        />

        <div className="grid gap-8 lg:grid-cols-[1.25fr_1fr] items-center">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 bg-amber-400/10 px-3 py-1 text-xs font-extrabold text-amber-300">
              <Sparkles size={14} /> Feito sob medida para TI & Concursos Fiscais/Tribunais
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-fg leading-tight">
              Pare de perder horas em PDFs de 150 páginas e editais confusos.
            </h2>
            <p className="text-sm text-fg-2 leading-relaxed">
              O <strong>GSN Concursos</strong> cruza automaticamente os editais oficiais com requisitos para{' '}
              <strong>Sistemas de Informação</strong>, monta seu ciclo semanal pela banca (FGV, Cebraspe, FCC, Vunesp e mais 12)
              e entrega <strong>flashcards em imagem gerados por IA</strong> prontos para memorização em 15 segundos.
            </p>

            <div className="grid gap-2.5 sm:grid-cols-2 pt-1 text-xs font-medium text-fg">
              <div className="flex items-center gap-2">
                <Check size={15} className="text-emerald-400 shrink-0" />
                <span>43+ Flashcards Visuais (imagens IA + download HD)</span>
              </div>
              <div className="flex items-center gap-2">
                <Check size={15} className="text-emerald-400 shrink-0" />
                <span>Aulas completas em 5 etapas + Quadro Digital</span>
              </div>
              <div className="flex items-center gap-2">
                <Check size={15} className="text-emerald-400 shrink-0" />
                <span>Raio-X comparativo de 16 bancas examinadoras</span>
              </div>
              <div className="flex items-center gap-2">
                <Check size={15} className="text-emerald-400 shrink-0" />
                <span>Cronômetro, Ciclo Semanal e Revisão Espaçada SM-2</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button variant="primary" size="md" onClick={() => handleSelectPlan('pro')} className="gap-2 font-bold">
                <Crown size={16} /> Quero o Plano Pro
              </Button>
              <Button variant="secondary" size="md" onClick={() => navigate('/estudos/flashcards')} className="gap-2">
                <BookOpen size={16} /> Ver Flashcards em Imagem IA
              </Button>
            </div>
          </div>

          {/* Mini Galeria Real dos Flashcards em Imagem IA */}
          <div className="grid grid-cols-2 gap-3">
            {SHOWCASE_CARDS.map((item) => (
              <div
                key={item.src}
                className="group overflow-hidden rounded-xl border border-line-strong bg-[#FAF6EC] shadow-md transition-transform hover:scale-[1.02]"
              >
                <img
                  src={item.src}
                  alt={item.title}
                  loading="lazy"
                  className="aspect-[4/5] w-full object-cover block"
                />
                <p className="border-t border-line bg-surface px-2.5 py-1.5 text-[10px] font-bold text-fg truncate">
                  {item.title}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Planos & Preços */}
      <section aria-label="Planos disponíveis" className="grid gap-5 lg:grid-cols-3">
        {/* Plano Gratuito */}
        <div className="flex flex-col justify-between rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-fg-3">Degustação</span>
              <Badge tone="neutral">Grátis</Badge>
            </div>
            <h3 className="mt-2 font-display text-xl font-extrabold text-fg">Plano Estudante Gratuito</h3>
            <p className="mt-1 text-3xl font-black text-fg">
              R$ 0 <span className="text-xs font-medium text-fg-3">/ para testar</span>
            </p>
            <ul className="mt-5 space-y-2.5 text-xs text-fg-2">
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Acesso ao Radar Nacional de Concursos</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Filtro de compatibilidade Sistemas de Informação</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Cronômetro, Ciclo Semanal e amostra de aulas</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Amostra dos Flashcards em Imagem IA</li>
            </ul>
          </div>
          <Button variant="secondary" size="md" className="mt-6 w-full font-bold" onClick={() => handleSelectPlan('free')}>
            {user ? 'Continuar Estudando' : 'Criar Conta Grátis'}
          </Button>
        </div>

        {/* Plano Pro Mensal (Destaque) */}
        <div className="relative flex flex-col justify-between rounded-2xl border-2 border-amber-400 bg-surface p-6 shadow-xl">
          <span className="absolute -top-3 right-5 rounded-full bg-amber-400 px-3 py-0.5 text-[10px] font-black uppercase tracking-wider text-slate-950 shadow">
            Mais Vendido
          </span>
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Acesso Mensal</span>
              <Badge tone="accent">Pro</Badge>
            </div>
            <h3 className="mt-2 font-display text-xl font-extrabold text-fg">Plano Pro Aprovação TI</h3>
            <p className="mt-1 text-3xl font-black text-fg">
              R$ 39,90 <span className="text-xs font-medium text-fg-3">/ mês</span>
            </p>
            <ul className="mt-5 space-y-2.5 text-xs text-fg">
              <li className="flex items-center gap-2"><Check size={14} className="text-amber-400 shrink-0" /> Todas as Aulas Estruturadas em 5 Etapas</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-amber-400 shrink-0" /> Todos os Flashcards em Imagem IA + Download HD</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-amber-400 shrink-0" /> Revisão Espaçada SM-2 + Banco de Questões & Simulados</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-amber-400 shrink-0" /> Dossiê completo de editais + Raio-X das 16 bancas</li>
            </ul>
          </div>
          <Button variant="primary" size="md" className="mt-6 w-full font-extrabold" onClick={() => handleSelectPlan('pro')}>
            Assinar Plano Pro
          </Button>
        </div>

        {/* Plano Anual Fundador */}
        <div className="flex flex-col justify-between rounded-2xl border border-line-strong bg-surface p-6 shadow-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Anual · Economize 48%</span>
              <Badge tone="ok">Fundador TI</Badge>
            </div>
            <h3 className="mt-2 font-display text-xl font-extrabold text-fg">Passe Anual Fundador</h3>
            <p className="mt-1 text-3xl font-black text-fg">
              R$ 247 <span className="text-xs font-medium text-fg-3">/ ano (12 meses)</span>
            </p>
            <ul className="mt-5 space-y-2.5 text-xs text-fg-2">
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Tudo do Plano Pro por 12 meses garantidos</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Todas as futuras atualizações e novos pacotes de flashcards IA</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Download ilimitado dos mapas visuais sketchnote</li>
              <li className="flex items-center gap-2"><Check size={14} className="text-emerald-400 shrink-0" /> Prioridade para solicitar novos concursos/editais no Radar</li>
            </ul>
          </div>
          <Button variant="secondary" size="md" className="mt-6 w-full font-bold border-emerald-500/40 hover:border-emerald-400" onClick={() => handleSelectPlan('founder')}>
            Garantir Passe Anual
          </Button>
        </div>
      </section>

      {/* Garantias & Acesso */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card title="1. Conta Individual" subtitle="Cada aluno tem seu próprio progresso isolado">
          <p className="text-xs text-fg-2 leading-relaxed">
            Seus concursos foco, cronômetro, acertos em simulados e fila SM-2 ficam salvos exclusivamente na sua conta.
          </p>
        </Card>
        <Card title="2. Liberação Automática" subtitle="Integração via Webhook Kiwify / Hotmart / Asaas">
          <p className="text-xs text-fg-2 leading-relaxed">
            Comprou com seu e-mail? O webhook libera o acesso Pro instantaneamente assim que o Pix ou cartão confirma.
          </p>
        </Card>
        <Card title="3. Sem Enrolação" subtitle="Feito para estudar hoje">
          <p className="text-xs text-fg-2 leading-relaxed">
            Interface limpa focada em memorização rápida, questões comentadas alternativa por alternativa e prazos reais.
          </p>
        </Card>
      </div>
    </div>
  );
}

export function AccountPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const selectedPlanParam = searchParams.get('plano');
  const authMe = useAuthMe();
  const user = authMe.data?.user ?? null;
  const hasAdmin = authMe.data?.has_admin ?? true;
  const publicMode = authMe.data?.public_mode ?? false;
  const [workspaceMode, updateWorkspaceMode] = useWorkspaceMode(user?.role);

  const [authTab, setAuthTab] = useState<'login' | 'register'>(() =>
    selectedPlanParam ? 'register' : 'login',
  );
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [bootstrapAdmin, setBootstrapAdmin] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authMsg, setAuthMsg] = useState<string | null>(null);

  useEffect(() => {
    if (selectedPlanParam) {
      setAuthTab('register');
    }
  }, [selectedPlanParam]);

  useEffect(() => {
    if (authMe.data) {
      setBootstrapAdmin(!authMe.data.has_admin && !authMe.data.public_mode);
    }
  }, [authMe.data]);

  const canUseAdmin =
    user?.role === 'admin' || (!user && !publicMode && !authMe.data?.require_auth);
  const adminUsers = useAdminUsers(Boolean(canUseAdmin && workspaceMode === 'admin'));
  const adminBilling = useAdminBilling(Boolean(canUseAdmin && workspaceMode === 'admin'));

  const resetUserScopedCache = async () => {
    queryClient.clear();
    await queryClient.invalidateQueries({ queryKey: keys.authMe() });
  };

  const loginMutation = useMutation({
    mutationFn: () => api.post<{ ok: boolean; user: AppUser }>('/api/auth/login', { email, password }),
    onSuccess: async () => {
      setAuthError(null);
      setAuthMsg('Sessão iniciada com sucesso!');
      await resetUserScopedCache();
    },
    onError: (err: Error) => {
      setAuthMsg(null);
      setAuthError(err.message);
    },
  });

  const registerMutation = useMutation({
    mutationFn: () =>
      api.post<{ ok: boolean; user: AppUser }>('/api/auth/register', {
        name,
        email,
        password,
        bootstrap_admin: bootstrapAdmin,
      }),
    onSuccess: async () => {
      setAuthError(null);
      setAuthMsg('Conta criada e sessão aberta!');
      await resetUserScopedCache();
    },
    onError: (err: Error) => {
      setAuthMsg(null);
      setAuthError(err.message);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => api.post('/api/auth/logout', {}),
    onSuccess: async () => {
      updateWorkspaceMode('student');
      setAuthMsg('Você saiu da conta.');
      await resetUserScopedCache();
    },
  });

  const upgradeUserMutation = useMutation({
    mutationFn: (payload: { user_id: string; plan: 'free' | 'pro' | 'founder' }) =>
      api.post('/api/admin/users/plan', { ...payload, plan_status: 'active' }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.adminUsers() });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Conta, Acesso & Perfil"
        title="Minha Conta & Modo de Uso"
        description="Gerencie sua assinatura, separe sua conta pessoal de estudo e (para administradores) alterne para o painel de curadoria e vendas."
        actions={
          <Link to="/planos">
            <Button variant="secondary" size="sm" className="gap-1.5">
              <Crown size={14} className="text-amber-400" /> Ver Planos
            </Button>
          </Link>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
        {/* Bloco 1: Identidade Atual ou Login/Cadastro */}
        <Card
          title={user ? `Olá, ${user.name}` : 'Entrar ou Criar Conta'}
          subtitle={
            user
              ? `${user.email} · ${PLAN_LABELS[user.plan] ?? user.plan}`
              : 'Crie contas individuais para cada aluno ou faça login com sua conta de Administrador.'
          }
        >
          {user ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-line bg-surface-2 p-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3">Perfil</span>
                  <p className="mt-1 text-sm font-extrabold text-fg flex items-center gap-1.5">
                    {user.role === 'admin' ? (
                      <>
                        <ShieldCheck size={15} className="text-amber-400" /> Administrador
                      </>
                    ) : (
                      <>
                        <UserCheck size={15} className="text-sky-400" /> Estudante
                      </>
                    )}
                  </p>
                </div>
                <div className="rounded-xl border border-line bg-surface-2 p-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3">Plano</span>
                  <p className="mt-1 text-sm font-extrabold text-fg">{PLAN_LABELS[user.plan] ?? user.plan}</p>
                </div>
                <div className="rounded-xl border border-line bg-surface-2 p-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3">Status</span>
                  <p className="mt-1 text-sm font-extrabold text-emerald-400 uppercase">{user.plan_status}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button variant="primary" size="sm" onClick={() => navigate('/estudos/aulas')} className="gap-1.5">
                  <BookOpen size={14} /> Ir para Minhas Aulas
                </Button>
                {user.plan === 'free' && (
                  <Button variant="secondary" size="sm" onClick={() => navigate('/planos')} className="gap-1.5">
                    <Crown size={14} className="text-amber-400" /> Fazer Upgrade Pro
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={logoutMutation.isPending}
                  onClick={() => logoutMutation.mutate()}
                  className="ml-auto gap-1.5 text-risk"
                >
                  <LogOut size={14} /> Sair da Conta
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedPlanParam && PLAN_LABELS[selectedPlanParam] && (
                <div className="flex items-center gap-2 rounded-xl border border-amber-400/40 bg-amber-400/10 px-3.5 py-2.5 text-xs font-semibold text-amber-300">
                  <Crown size={14} className="shrink-0 text-amber-400" />
                  <span>
                    Plano selecionado: <strong>{PLAN_LABELS[selectedPlanParam]}</strong> — crie ou entre na sua conta com o mesmo e-mail do pagamento.
                  </span>
                </div>
              )}
              <div className="flex gap-1.5 rounded-xl border border-line bg-surface-2 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setAuthTab('login');
                    setAuthError(null);
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition-all ${
                    authTab === 'login' ? 'bg-amber-400 text-slate-950' : 'text-fg-2 hover:text-fg'
                  }`}
                >
                  <KeyRound size={14} /> Já tenho conta (Entrar)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAuthTab('register');
                    setAuthError(null);
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition-all ${
                    authTab === 'register' ? 'bg-amber-400 text-slate-950' : 'text-fg-2 hover:text-fg'
                  }`}
                >
                  <UserPlus size={14} /> Criar Nova Conta
                </button>
              </div>

              {authTab === 'login' ? (
                <form
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    loginMutation.mutate();
                  }}
                >
                  <label className="block space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-fg-3">E-mail</span>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="seu@email.com"
                      className="h-10 w-full rounded-lg border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none focus:border-amber-400"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-fg-3">Senha</span>
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••"
                      className="h-10 w-full rounded-lg border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none focus:border-amber-400"
                    />
                  </label>
                  {authError && <p className="text-xs font-semibold text-risk">{authError}</p>}
                  {authMsg && <p className="text-xs font-semibold text-emerald-400">{authMsg}</p>}
                  <Button type="submit" variant="primary" size="md" disabled={loginMutation.isPending} className="w-full font-bold">
                    Entrar na Plataforma
                  </Button>
                </form>
              ) : (
                <form
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    registerMutation.mutate();
                  }}
                >
                  <label className="block space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-fg-3">Nome completo</span>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Ex.: Gabriel Silva"
                      className="h-10 w-full rounded-lg border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none focus:border-amber-400"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-fg-3">E-mail</span>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="seu@email.com"
                      className="h-10 w-full rounded-lg border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none focus:border-amber-400"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-fg-3">Senha (mínimo 6 caracteres)</span>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Crie uma senha forte"
                      className="h-10 w-full rounded-lg border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none focus:border-amber-400"
                    />
                  </label>

                  {!hasAdmin && !publicMode && (
                    <label className="flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-200 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={bootstrapAdmin}
                        onChange={(e) => setBootstrapAdmin(e.target.checked)}
                      />
                      Ativar como conta Administrador / Fundador (1º acesso local)
                    </label>
                  )}

                  {authError && <p className="text-xs font-semibold text-risk">{authError}</p>}
                  {authMsg && <p className="text-xs font-semibold text-emerald-400">{authMsg}</p>}
                  <Button type="submit" variant="primary" size="md" disabled={registerMutation.isPending} className="w-full font-bold">
                    Criar Conta e Começar
                  </Button>
                </form>
              )}
            </div>
          )}
        </Card>

        {/* Bloco 2: Chave Modo Estudante vs Modo Admin (visível só para Admin ou modo local do dono) */}
        {canUseAdmin ? (
          <Card
            title="Visão da Plataforma (Estudar vs. Administrar)"
            subtitle="Por padrão, a plataforma esconde as telas técnicas de auditoria para ficar 100% pronta para o aluno/comprador."
          >
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => updateWorkspaceMode('student')}
                  className={`rounded-xl border-2 p-4 text-left transition-all ${
                    workspaceMode === 'student'
                      ? 'border-amber-400 bg-amber-400/10'
                      : 'border-line bg-surface-2 hover:border-line-strong'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <Compass size={18} className="text-amber-400" />
                    {workspaceMode === 'student' && <Badge tone="accent">Ativo</Badge>}
                  </div>
                  <p className="mt-2 text-sm font-extrabold text-fg">Modo Estudante (Comercial)</p>
                  <p className="mt-1 text-xs text-fg-2">
                    Menu limpo focado em Concursos, Aulas, Flashcards IA, Questões e Planos — exatamente como o cliente vê.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => updateWorkspaceMode('admin')}
                  className={`rounded-xl border-2 p-4 text-left transition-all ${
                    workspaceMode === 'admin'
                      ? 'border-emerald-400 bg-emerald-500/10'
                      : 'border-line bg-surface-2 hover:border-line-strong'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <ShieldCheck size={18} className="text-emerald-400" />
                    {workspaceMode === 'admin' && <Badge tone="ok">Ativo</Badge>}
                  </div>
                  <p className="mt-2 text-sm font-extrabold text-fg">Modo Admin & Curadoria</p>
                  <p className="mt-1 text-xs text-fg-2">
                    Libera Mesa de Validação, Revisão de Editais, Padronização de Cargos, Esteira, Diagnóstico e Gestão de Alunos.
                  </p>
                </button>
              </div>

              <div className="rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg-2 flex items-start gap-2.5">
                <Lock size={15} className="text-fg-3 shrink-0 mt-0.5" />
                <span>
                  Alunos que criarem conta como <strong>Estudante</strong> nunca enxergam essa opção e têm os dados
                  de estudo (concursos foco, flashcards SM-2 e simulados) isolados pelo servidor.
                </span>
              </div>
            </div>
          </Card>
        ) : (
          <Card title="Seu Ambiente Privado de Aprovação" subtitle="Progresso 100% separado na sua conta">
            <div className="space-y-3 text-xs text-fg-2 leading-relaxed">
              <p className="flex items-center gap-2 text-fg font-semibold">
                <Award size={16} className="text-amber-400 shrink-0" /> Todos os seus concursos foco, sessões cronometradas e cartões SM-2 são individuais.
              </p>
              <p>
                Explore os <strong>Flashcards Visuais em Imagem (IA)</strong>, monte seu <strong>Ciclo Semanal</strong> e acompanhe os editais compatíveis com <strong>Sistemas de Informação</strong>.
              </p>
            </div>
          </Card>
        )}
      </div>

      {/* Painel SaaS Admin: Gestão de Alunos & Webhook de Vendas */}
      {canUseAdmin && workspaceMode === 'admin' && (
        <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
          <Card
            title="Clientes & Alunos Cadastrados"
            subtitle="Libere acesso Pro ou Fundador com 1 clique ou acompanhe novos cadastros."
          >
            {adminUsers.isLoading ? (
              <p className="text-xs text-fg-3">Carregando usuários...</p>
            ) : !adminUsers.data?.length ? (
              <p className="text-xs text-fg-3">
                Nenhum usuário cadastrado ainda. Crie sua conta Administrador ao lado ou receba seu primeiro comprador!
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-fg-3 uppercase text-[10px]">
                      <th className="py-2 pr-3">Aluno</th>
                      <th className="py-2 pr-3">E-mail</th>
                      <th className="py-2 pr-3">Plano</th>
                      <th className="py-2 text-right">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {adminUsers.data.map((u) => (
                      <tr key={u.id}>
                        <td className="py-2.5 pr-3 font-semibold text-fg">
                          {u.name} {u.role === 'admin' && <Badge tone="accent">Admin</Badge>}
                        </td>
                        <td className="py-2.5 pr-3 text-fg-2">{u.email}</td>
                        <td className="py-2.5 pr-3">
                          <Badge tone={u.plan === 'free' ? 'neutral' : 'ok'}>
                            {u.plan.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="py-2.5 text-right space-x-1">
                          <Button
                            size="sm"
                            variant={u.plan === 'pro' ? 'primary' : 'ghost'}
                            disabled={upgradeUserMutation.isPending}
                            onClick={() => upgradeUserMutation.mutate({ user_id: u.id, plan: 'pro' })}
                          >
                            Ativar Pro
                          </Button>
                          <Button
                            size="sm"
                            variant={u.plan === 'free' ? 'secondary' : 'ghost'}
                            disabled={upgradeUserMutation.isPending}
                            onClick={() => upgradeUserMutation.mutate({ user_id: u.id, plan: 'free' })}
                          >
                            Gratuito
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card
            title="Webhook Automático de Pagamentos"
            subtitle="Conecte Kiwify, Hotmart, Asaas ou Stripe para liberar o Plano Pro automaticamente após o Pix/Cartão."
          >
            <div className="space-y-3 text-xs">
              <div className="rounded-xl border border-line bg-surface-2 p-3 space-y-1">
                <p className="font-bold text-fg flex items-center gap-1.5">
                  <Webhook size={14} className="text-amber-400" /> Endpoint Webhook POST:
                </p>
                <code className="block break-all rounded bg-bg px-2 py-1.5 font-mono text-[11px] text-amber-300">
                  /api/billing/webhook
                </code>
                <p className="text-fg-3 text-[11px]">
                  Defina <code>RADAR_BILLING_SECRET</code> no ambiente e envie no header{' '}
                  <code>X-Webhook-Secret</code>.
                </p>
              </div>

              <div className="space-y-1.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-fg-3">
                  Últimos eventos recebidos
                </p>
                {!adminBilling.data?.length ? (
                  <p className="text-fg-3">Nenhuma notificação de pagamento recebida ainda.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {adminBilling.data.slice(0, 6).map((ev) => (
                      <li key={ev.id} className="py-2 flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-fg">{ev.email}</p>
                          <p className="text-[10px] text-fg-3">{ev.provider} · {ev.event_type}</p>
                        </div>
                        <Badge tone="ok">{ev.plan}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
