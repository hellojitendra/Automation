# WordPress Yoast SEO Bulk Updater

A Python script to bulk insert Yoast SEO metadata (focus keyphrases, SEO titles, meta descriptions, breadcrumb titles, and synonyms) into WordPress pages/posts via the REST API. Supports both Yoast Free and Premium features.

## Prerequisites

- **Python 3.6+** installed on your system
- **pip** (Python package installer)
- **WordPress site** with:
  - Yoast SEO plugin (Free or Premium) installed and activated
  - The companion plugin `enable-yoast-rest-api.php` installed and activated (enables Yoast meta fields via REST API)
  - Register Yoast meta fields with the REST API so the script can read/write them.

    Add the following to your theme's `functions.php` or a site-specific plugin. The function name is generic; you may rename it to avoid conflicts.

```php
<?php
add_action( 'init', 'register_yoast_meta_for_rest' );

function register_yoast_meta_for_rest() {

    // Post types to register meta on — adjust to match your LMS/plugin
    $post_types = [ 'page', 'post', 'sfwd-courses', 'sfwd-lessons', 'sfwd-topic', 'lesson', 'course' ];

    // Yoast SEO meta fields
    $meta_fields = [
        // Yoast FREE
        '_yoast_wpseo_focuskw'              => 'string',
        '_yoast_wpseo_title'                => 'string',
        '_yoast_wpseo_metadesc'             => 'string',
        '_yoast_wpseo_bctitle'              => 'string',
        '_yoast_wpseo_canonical'            => 'string',
        '_yoast_wpseo_meta-robots-noindex'  => 'string',
        '_yoast_wpseo_meta-robots-nofollow' => 'string',

        // Yoast PREMIUM
        '_yoast_wpseo_keywordsynonyms'      => 'string',
        '_yoast_wpseo_focuskeywords'        => 'string',
    ];

    foreach ( $post_types as $post_type ) {
        foreach ( $meta_fields as $meta_key => $meta_type ) {
            register_meta( 'post', $meta_key, [
                'object_subtype' => $post_type,
                'type'           => $meta_type,
                'single'         => true,
                'show_in_rest'   => true,
                'auth_callback'  => function() {
                    return current_user_can( 'edit_posts' );
                },
            ] );
        }
    }
}
```
- **WordPress Application Password** for authentication (generate in WP Admin > Users > Your Profile)

## Configuration

Edit the configuration section in insert-yoast-seo.py:

```python
WP_BASE_URL     = "https://your-wordpress-site.com"  # No trailing slash
WP_USERNAME     = "your-email@example.com"           # From WP Admin
WP_APP_PASSWORD = "your-application-password"       # From WP Admin
DEBUG = True   # Set to False to reduce output
```

Edit SEO entries in `seo_data.json`. The script loads SEO rows from that file (a JSON array of objects).

## Usage

Run the script:

`ash
python insert-yoast-seo.py
`

The script will:
1. Verify authentication
2. Find each post/page by slug
3. Update Yoast SEO metadata
4. Trigger Yoast's server-side analysis

## Notes

- This script triggers server-side Yoast analysis. For full analysis (including readability), open each page in the WordPress editor and save once.
- The companion plugin enable-yoast-rest-api.php is required for the REST API to expose Yoast meta fields.

## License

MIT License - see LICENSE file for details.
