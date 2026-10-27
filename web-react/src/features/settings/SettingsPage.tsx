import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { keys, usePreferences } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import type { Preferences } from '@/lib/types';

const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
  'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
];

const priorities: Record<string, string> = {
  equilibrado: 'Equilibrado',
  proximidade: 'Proximidade',
  prazo: 'Prazo',
};

export function SettingsPage() {
  const queryClient = useQueryClient();
  const preferences = usePreferences();
  const [saved, setSaved] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: Preferences) => api.post<Preferences>('/api/preferencias', body),
    onSuccess: () => {
      setSaved('Preferências salvas no arquivo local.');
      void queryClient.invalidateQueries({ queryKey: keys.preferences() });
    },
    onError: () => setSaved(null),
  });

  if (preferences.isLoading) {
    return (
      <>
        <PageHeader eyebrow="Preferências" title="Configurações" />
        <SkeletonRows rows={4} />
      </>
    );
  }

  if (preferences.isError || !preferences.data) {
    return (
      <>
        <PageHeader eyebrow="Preferências" title="Configurações" />
        <Card>
          <ErrorState
            message={preferences.error?.message ?? 'Preferências indisponíveis.'}
            onRetry={() => preferences.refetch()}
          />
        </Card>
      </>
    );
  }

  const data = preferences.data;

  return (
    <>
      <PageHeader
        eyebrow="Preferências"
        title="Configurações"
        description="Preferências geográficas e de prioridade são gravadas no arquivo local do Radar. A busca nacional continua disponível; a região apenas prioriza."
      />

      <div className="grid gap-3 xl:grid-cols-[1.2fr_1fr]">
        <Card title="Preferências de busca" subtitle="Aplicadas à priorização da carteira, nunca à exclusão de oportunidades.">
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              save.mutate({
                reference_municipio: (form.get('municipio') as string)?.trim() || null,
                reference_uf: (form.get('uf') as string) || null,
                interest_states: ((form.get('states') as string) ?? '')
                  .split(',')
                  .map((value) => value.trim().toUpperCase())
                  .filter(Boolean),
                practical_distance_km: Number(form.get('distance')) || null,
                priority: (form.get('priority') as string) || 'equilibrado',
              });
            }}
          >
            <Field label="Município de referência" hint="Opcional. Usado para distância em linha reta.">
              <input
                name="municipio"
                defaultValue={data.reference_municipio ?? ''}
                placeholder="Ex.: Recife"
                className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-sm text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
              />
            </Field>

            <Field label="UF de referência" hint="Opcional. Não restringe a busca nacional.">
              <select
                name="uf"
                defaultValue={data.reference_uf ?? ''}
                className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2 text-sm text-fg outline-none focus:border-accent/60"
              >
                <option value="">Não definir</option>
                {UFS.map((uf) => (
                  <option key={uf} value={uf}>{uf}</option>
                ))}
              </select>
            </Field>

            <Field label="Estados de interesse" hint="Separados por vírgula. Priorizam, não eliminam.">
              <input
                name="states"
                defaultValue={data.interest_states.join(', ')}
                className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-sm text-fg outline-none focus:border-accent/60"
              />
            </Field>

            <Field label="Distância prática (km)" hint="Distância em linha reta; não é distância rodoviária.">
              <input
                name="distance"
                type="number"
                min={0}
                max={5000}
                defaultValue={data.practical_distance_km ?? ''}
                className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-sm tabular text-fg outline-none focus:border-accent/60"
              />
            </Field>

            <Field label="Prioridade" hint="Muda a ordem da carteira, não os fatos.">
              <select
                name="priority"
                defaultValue={data.priority}
                className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2 text-sm text-fg outline-none focus:border-accent/60"
              >
                {Object.entries(priorities).map(([value, text]) => (
                  <option key={value} value={value}>{text}</option>
                ))}
              </select>
            </Field>

            <div className="sm:col-span-2 flex flex-wrap items-center gap-3 border-t border-line pt-3">
              <Button type="submit" variant="primary" disabled={save.isPending}>
                Salvar preferências
              </Button>
              {save.isError && <span className="text-2xs text-risk">{(save.error as Error).message}</span>}
              {saved && !save.isPending && <span className="text-2xs text-ok">{saved}</span>}
            </div>
          </form>
          <p className="mt-3 text-2xs text-fg-3">
            Persistência: arquivo de configuração local do Radar. Não há sincronização entre dispositivos.
          </p>
        </Card>

        <div className="space-y-3">
          <Card title="Interface" subtitle="Preferências visuais guardadas apenas neste navegador.">
            <label className="flex items-center justify-between gap-3 text-xs text-fg-2">
              <span>
                Menu lateral recolhido
                <span className="mt-0.5 block text-2xs text-fg-3">
                  A preferência é lembrada localmente e não altera os dados.
                </span>
              </span>
              <input
                type="checkbox"
                defaultChecked={localStorage.getItem('radar.sidebar.collapsed') === '1'}
                onChange={(event) => {
                  localStorage.setItem('radar.sidebar.collapsed', event.target.checked ? '1' : '0');
                  window.dispatchEvent(new Event('radar:sidebar'));
                }}
                className="size-4 accent-[var(--color-accent)]"
              />
            </label>
            <p className="mt-2 text-2xs text-fg-3">
              O menu também pode ser recolhido pelo botão no topo da barra lateral.
            </p>
          </Card>

          <Card title="Sobre esta versão" subtitle="Contrato e limites do produto.">
            <dl className="grid grid-cols-[110px_1fr] gap-y-2 text-2xs">
              <dt className="text-fg-3">Interface</dt>
              <dd className="text-fg-2">Radar de Concursos — frontend de produto (Fase 46)</dd>
              <dt className="text-fg-3">Dados</dt>
              <dd className="text-fg-2">SQLite local; nenhuma confirmação automática de campo</dd>
              <dt className="text-fg-3">API</dt>
              <dd className="text-fg-2">Contrato v1 preservado em GET /api/concursos</dd>
              <dt className="text-fg-3">Privacidade</dt>
              <dd className="text-fg-2">Sem conta, sem telemetria e sem envio a terceiros</dd>
              <dt className="text-fg-3">Operação</dt>
              <dd className="text-fg-2">Painéis técnicos preservados em /legacy/</dd>
            </dl>
          </Card>
        </div>
      </div>
    </>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-2xs font-medium text-fg-2">{label}</span>
      {children}
      {hint && <span className="text-2xs text-fg-3">{hint}</span>}
    </label>
  );
}
