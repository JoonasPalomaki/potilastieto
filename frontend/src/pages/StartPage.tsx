import { Link } from 'react-router-dom';

const StartPage = () => {
  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Tervetuloa</p>
        <h2 className="text-3xl font-bold text-slate-100">Potilastietojärjestelmän aloitussivu</h2>
        <p className="text-sm text-slate-300">
          Aloita työskentely valitsemalla jokin keskeisistä toiminnoista. Näet nopeasti potilaslistan, voit käynnistää
          ensikäynnin ajanvarauksesta tai lisätä järjestelmään uuden potilaan.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-100">Potilaslista</h3>
          <p className="mt-2 text-sm text-slate-300">
            Selaa järjestelmän potilaita, tarkastele perustietoja ja seuraa hoidon etenemistä. Potilaslistalta löydät
            tunnisteet ja ajantasaisen tilan.
          </p>
          <Link
            to="/patients"
            className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-sky-400 transition hover:text-sky-300"
          >
            Siirry potilaslistaan
            <span aria-hidden="true">→</span>
          </Link>
        </article>

        <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-100">Ensikäynnin käynnistys</h3>
          <p className="mt-2 text-sm text-slate-300">
            Käynnistä ensikäynti olemassa olevalle ajanvaraukselle. Valmistele hoitopolku, kirjaa lähtötiedot ja varmista,
            että potilaan ensikäynti käynnistyy sujuvasti.
          </p>
          <Link
            to="/first-visit"
            className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-sky-400 transition hover:text-sky-300"
          >
            Avaa ensikäynnin näkymä
            <span aria-hidden="true">→</span>
          </Link>
        </article>

        <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 shadow-sm md:col-span-2">
          <h3 className="text-lg font-semibold text-slate-100">Uuden potilaan luonti</h3>
          <p className="mt-2 text-sm text-slate-300">
            Lisää järjestelmään uusi potilas. Täytä perustiedot, liitä hoitopolku ja varmista, että potilas on heti valmis
            ajanvarausten tekemiseen.
          </p>
          <p className="mt-4 text-sm text-slate-400">
            Uuden potilaan luonti löytyy potilaslistan työkalupalkista. Valitse &quot;Lisää potilas&quot; ja seuraa ohjeita.
          </p>
          <Link
            to="/patients"
            className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-sky-400 transition hover:text-sky-300"
          >
            Siirry luomaan uutta potilasta
            <span aria-hidden="true">→</span>
          </Link>
        </article>
      </div>
    </section>
  );
};

export default StartPage;
