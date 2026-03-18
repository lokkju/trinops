// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://trino.ps',
	integrations: [
		starlight({
			title: 'trino.ps',
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/lokkju/trinops' },
				{ icon: 'external', label: 'PyPI', href: 'https://pypi.org/project/trinops/' },
			],
			customCss: ['./src/styles/custom.css'],
			sidebar: [
				{
					label: 'Start Here',
					items: [
						{ label: 'Getting Started', slug: 'docs/getting-started' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'TUI Dashboard', slug: 'docs/tui' },
						{ label: 'Schema Search', slug: 'docs/schema' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Configuration', slug: 'docs/configuration' },
						{ label: 'CLI Reference', slug: 'docs/cli' },
						{ label: 'Python Library', slug: 'docs/library' },
					],
				},
			],
		}),
	],
});
