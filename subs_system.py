import xml.etree.ElementTree as ET
from nltk.corpus import lin_thesaurus as lin
from nltk.corpus import wordnet as wn
import re
import lesk as LESK
import operator

# This file consists of several algorithm to get the similar words
# from the goal word.


k = 10 # the number of top kth lin similarity words

#return wn similarity of two synsets according to metric
def wnsensesim(synset1, synset2, metric):

    if metric == 'path_similarity':
        return wn.path_similarity(synset1, synset2)
    elif metric == 'lch_similarity':
        return wn.lch_similarity(synset1, synset2)
    elif metric == 'wup_similarity':
        return wn.wup_similarity(synset1, synset2)
    else:#add more similarity measures e.g., jcn
        print "Unsupported wn similarity measure requested"


#return the wn similarity of word to synset - maximised over the senses of word, determined by metric
def wnss(word, synset, metric, pos=wn.NOUN):

    senses = wn.synsets(word, pos)
    if len(senses)==0:
        print "Warning: no WN synsets for "+word
    max = 0
    for sense in senses:
        sim = wnsensesim(sense, synset, metric)
        if sim > max: max = sim
    return max

#get prevalent sense
def prevalent_sense(word,pos=wn.NOUN, metric='path_similarity'):
    # transfer the pos to the form lin similarity
    if (pos=='a') or (pos=='r'):
        lin_type='simA.lsp'
    elif pos=='v':
        lin_type='simV.lsp'
    else:
        lin_type='simN.lsp'
    distthes = lin.scored_synonyms(word, fileid=lin_type)
    sortedthes = sorted(distthes, key=operator.itemgetter(1), reverse=True)[0:k]

    scores = {}  #dict for the scores for each sense which will be contributed to by each neighbour

    for wnsynset in wn.synsets(word,pos):
        #initialise scores for each synset as 0
        scores[wnsynset.name] = 0

    for (neigh, dss) in sortedthes:
        if len(wn.synsets(neigh))>0: #check neighbour is in WN otherwise all sims will be 0


            sum = 0  #this will be the sum of wnss scores for this distributional neighbour (summed over all senses)
            neighscores = {}  #this stores the wnss scores for each sense for this neighbour
                            #it could be a list with index corresponding to WN synset number
                            #will need to divide by sum and times by dss before adding to the sum over all distributional neighbours for each sense
            for wnsynset in wn.synsets(word,pos): # word = film
                wnss_score = wnss(neigh, wnsynset,metric=metric,pos=pos)#look up wnss score for this neighbour and this sense
                sum += wnss_score  #add it to the sum over all senses for the neighbour
                neighscores[wnsynset.name] = wnss_score  #store it in dictionary so that each value can later be divided by sum
            for wnsynset in wn.synsets(word,pos):#second loop is needed to divide by sum (which is not known until completion of first loop)
                                                #sum will be different for each neighbour so it is not a constant which can be ignored
                if sum==0:
                    scores[wnsynset.name] = 0
                else:
                    scores[wnsynset.name] += dss * neighscores[wnsynset.name] / sum  #weight the score for each sense (according to this neighbour)
                                                                    # by its dss score and inversely by the sum of wnss scores for this neighbour
                                                                    # and add to the total for this sense
        else:
            print "Warning: ignoring distributional neighbour "+neigh+" : not in WordNet as noun"  #this is likely to happen when distributional neighbours are proper nouns see 'hull' example
                                                #probably should modifiy code so that it is the top k neighbours excluding words not in WN


    scoreslist = [scoretuple for scoretuple in scores.items()]
    sortedscores = sorted(scoreslist, key=operator.itemgetter(1), reverse=True)
    return sortedscores, sortedthes


# Getting the infomation from the origin text, like pos, context, lexelt,
# target word.
def get_sents_targets():
    #the original sentence path file, given by lab
    sents_path='/Users/yulong/Documents/code/myspace/python/term2/my_assign1/lexsub_trial.sents.txt'
    targets_path='/Users/yulong/Documents/code/myspace/python/term2/my_assign1/lexsub_trial.targets.tsv'

    f = open(sents_path)
    sents_result = []
    for i in f:
        sents_result.append(i)

    ff = open(targets_path)
    head_index = []
    ori_names = []
    lexelt = []
    pos_arr = []
    for j in ff:
        index = int((j.split("\t")[-1]).split("\n")[0])

        pos = (j.split("\t")[0]).split(".")[-1]
        pos_arr.append(pos)
        ori_name = (j.split("\t")[0]).split(".")[0]
        ori_names.append(ori_name)
        head_index.append(index)
        lexelt.append(j.split("\t")[0])

    head_words = []
    for index, sent in enumerate(sents_result):
        #print "index:%r" % index
        head_index_of_sent = head_index[index]
        sents_arr = sent.split(" ")
        if head_index_of_sent == 0:
            head_words.append(sents_arr[head_index_of_sent])
        else:
            head_words.append(sents_arr[head_index_of_sent-1])
    return sents_result, head_words, lexelt,  pos_arr, ori_names

# get_substitution parameters doc:
# sents: the sentence of current sentence
# head_words: the target word
# lexelt: the target word with pos, like 'bright.a'
# pos_arr: the pos array of all the trial sentence
# ori_name: the original form of head word, like 'bright' instead of 'brighter'
# method: this is the main variant of the methods.
#        avalible option: 'adapted' for adapted version of LESK
#        avalible option: 'original' for original version of LESK
#        avalible option: 'simple' for simple version of LESK
#        avalible option: 'new' for new version of LESK
#        avalible option: 'lin' for lin similarity of finding substitution as baseline
#        avalible option: 'prevalent' for prevalent sense of finding substitution as baseline
# metric: the option of similarity method

def get_substitution(sents, head_words, lexelt, pos_arr, ori_names, method="adapted",metric='path_similarity',stop=True):
    _file = open('./BL.out','a')

    sent_id=0
    for index, sent in enumerate(sents):
        sent_id +=1
        pos = pos_arr[index]
        head_word = head_words[index]

        # whether use lesk or not
        if (method == 'lin') or (method == 'prevalent'):
            result = ''
        else:
            result = apply_lesk(sent, head_word, pos_arr,index, method=method, stop=stop)

        if not result:
        # use baseline(lin prevalent), head_word is the origin format, like bright, not brighter, brigetest
            head_word = ori_names[index]
            result = apply_lin(pos, head_word, method, metric)
            _file.write ("%s %r :: %s\n" % (lexelt[index], sent_id, result))
        else:
            _file.write ("%s %r :: %s\n" % (lexelt[index], sent_id, result))

    _file.close


# process the head_word with lesk algorithms
def apply_lesk(sent, head_word, pos_arr, index, method='adapted',stop=True):
    if method == "adapted":
        answer = LESK.adapted_lesk(sent, head_word, pos_arr[index],stop=False)
    elif method == 'new':
        answer = LESK.new_lesk(sent, head_word, pos_arr[index],stop=stop)
    elif method == 'original':
        answer = LESK.original_lesk(sent, head_word)
    elif method == 'simple':
        answer = LESK.simple_lesk(sent, head_word)

    # no synset of answer
    if answer is None:
        return ''

    if (head_word in answer.lemma_names):
        answer.lemma_names.remove(head_word)

    if not answer.lemma_names:
        return ''
    else:
        return answer.lemma_names[0]

#baseline methods(lin prevalent)
def apply_lin(pos, head_word, method='lin', metric='path_similarity'):
    [senses, lin] = prevalent_sense(head_word, pos=pos, metric=metric)
    result = ""
    if method == 'prevalent':
        for sense in senses:
            if head_word not in sense[0]:
                #print "head_word%r, sense:%r" %(head_word,sense[0])
                result =  wn.synset(sense[0]).name.split(".")[0]
                #print "result"
                #print result
                return result
    else:
        if not lin:
            result = ""
        else:
            result = lin[0][0]
    return result


head_index=[]
sents=[]
lexelt =[]
sents, head_index, lexelt, pos_arr, ori_names = get_sents_targets()

# method option: baseline{lin,prevalent}, LESK{adapted, original, simple, new}.
# metric option: path_similarity, lch_similarity, wup_similarity
# stop can be only uesd for the adapted lesk and it is a boolean type
get_substitution(sents, head_index, lexelt, pos_arr, ori_names, method='adapted')#, metric='wup_similarity')#, stop=False)
