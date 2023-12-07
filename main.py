from APICalls import get_collaborations_since

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    files = get_collaborations_since('2023-11-09T00:00:00Z', 'apache', 'commons-io',
                                     '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')

